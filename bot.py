# This Python file uses the following encoding: utf-8
from mongoengine import *
from pymongo import read_preferences
from models import *
import sys
from pprint import pprint
import telepot
import time
import settings as settings
import staticStrings
import requests
import json
import datetime
import redis
from threading import Thread
from khayyam import *
import unicodedata
import locale
from dateutil import tz,parser
from flask import Flask, request
import dateutil.parser
import urllib
import re
import unidecode
from utils import *
import persianiser as prsnr
try:
  from Queue import Queue
except ImportError:
  from queue import Queue
reload(sys)
sys.setdefaultencoding("utf-8")
connect(settings.MONGO_DATABASE,read_preference=read_preferences.ReadPreference.PRIMARY ,host=settings.MONGO_HOST, port=settings.MONGO_PORT,
        username=settings.MONGO_USERNAME, password=settings.MONGO_PASSWORD)

bots = {}

TEMPORARY_UPLOAD_FOLDER = 'media'

from_zone = tz.gettz('UTC')
to_zone = tz.gettz('Asia/Tehran')

locale.setlocale(locale.LC_ALL, 'en_US.utf8')

rds = redis.StrictRedis(host='localhost', port=6379, db=1)

hide_keyboard = {'hide_keyboard': True}

class StoreBot(telepot.Bot):
    def __init__(self, *args, **kwargs):
      super(StoreBot, self).__init__(*args, **kwargs)
      self.botToken = args[0]
      self._answerer = telepot.helper.Answerer(self)
      bot = BotModel.objects(botToken=self.botToken).first()
      if(bot):
        self.id = str(bot.id)
        self.phoneNumber = bot.adminPhoneNumber
        self.logChannel = bot.sysLogChannel
        self.adminChannel = bot.adminLogChannel
        self.accountOwner = bot.accountOwner
        self.apiToken = bot.apiToken
        self.maxWage = bot.maxWage
        self.username = bot.username
        self.botName = bot.name
        self.donateMode = bot.donateMode
        self.postalCodeRequired = bot.postalCodeRequired
        self.skipSingleProduct = bot.skipSingleProduct
        self.mainKeyboard = bot.schema['mainKeyboard']
        print "==> %s started!"%(bot.username)

    def initUser(self, chatID, msg):
      tempChatID = self.username + '-' + chatID
      usr = dict()
      name = ''
      if 'first_name' in msg['chat']:
        name += msg['chat']['first_name']
      if 'last_name' in msg['chat']:
        name += ' '+msg['chat']['last_name']
      usr['name'] = name;
      usr['number'] = ''
      usr['amount'] = ''
      usr['address'] = ''
      usr['org'] = 0
      usr['state'] = 0
      usr['note'] = ''
      usr['cart'] = []
      usr['count'] = 0
      usr['product'] = ''
      usr['type'] = ''
      usr['seq'] = []
      usr['productType'] = ''
      usr['extraParameterResults'] = {}
      usr['extraParameters'] = []
      print 'user inited'
      rds.set(tempChatID,json.dumps(usr))
      return usr

    def isAddressRequired(self, chatID):
      usr = self.getUser(chatID)
      isRequired = False
      for itm in usr['cart']:
        if(itm['productID'] != 'donate'):
          prd = ProductModel.objects(id=itm['productID']).first()
          if prd:
            if prd.addressRequired:
              return True
      return False

    def validateNumber(self, chatID,inputStr):
      res = convertToDigit(inputStr)
      usr = self.getUser(chatID)
      lastStep = False 
      if usr['type'] == 'donate':
        lastStep = True
      if res.find('0') == 0:
        res = res[1:]
      if res.find('98') != 0:
        res = '98' + res

      if len(res) != 12:
        self.sendMsg(chatID,staticStrings.numberValueError)
      else:
        self.updateUser(chatID,'number',res)
        rds.set(res,chatID)

        if not self.isAddressRequired(chatID):
          self.updateUser(chatID,'state',2)
          self.validateDetail(chatID)
        else:
          self.updateUser(chatID,'state',7)
          if(self.postalCodeRequired):
            self.sendMsg(chatID,staticStrings.getAddressAndPostalCode)
          else:
            self.sendMsg(chatID,staticStrings.getAddress)

    def validateDetail(self, chatID):
      usr = self.getUser(chatID)
      note = ''
      amount = 0
      tempLst = []
      wge = self.calcWage(chatID)
      hasProduct = False
      for itm in usr['cart']:
        amount += int(itm['amount'])
        tempStr = ''
        if itm['product'] == 'donate' or itm['productType'] == 'donate':
          tempStr = itm['note']
        else:
          tempStr = itm['note']%(persianiser(itm['count']))
          hasProduct = True

        for extraItm in itm['extraParameterResults']:
          tempStr += '، '+ extraItm +':'+ itm['extraParameterResults'][extraItm]
        tempLst.append(tempStr)
      note = u' و '.join(tempLst)
      if hasProduct:
        note = u'خرید ' + note

      if len(note) > 100:
        note = note[:97] + u'...'
      amount += wge
      amount = str(amount)

      self.updateUser(chatID,'state',6)
      if hasProduct == False:
        self.sendMsg(chatID,staticStrings.validateDetail%(humanizeNumber(usr['number']),humanizeAmount(amount),note),settings.KEYBOARDS['confirmItem'])
      else:
        self.sendMsg(chatID,staticStrings.validateDetailWithAddress%(humanizeNumber(usr['number']),humanizeAmount(amount),note,usr['address']),settings.KEYBOARDS['confirmItem'])



    def getUser(self, chatID):
      tempChatID = self.username + '-' + chatID
      usr = json.loads(rds.get(tempChatID))
      return usr
    def updateUser(self, chatID,ky,val):
      tempChatID = self.username + '-' + chatID
      usrData = rds.get(tempChatID)
      if usrData:
        usr = json.loads(usrData)
        usr[ky] = val
        rds.set(tempChatID,json.dumps(usr))

    def getAddress(self, chatID,inputStr):
      self.updateUser(chatID,'address',inputStr)
      self.updateUser(chatID,'state',5)
      self.validateDetail(chatID)

    def getUserDetail(self, chatID,ky):
      tempChatID = self.username + '-' + chatID
      usr = json.loads(rds.get(tempChatID))
      if ky in usr:
        return usr[ky]
      else:
        return None

    def goBack(self, chatID,steps=1):
      usr = self.getUser(chatID)
      newSeq = usr['seq'][:len(usr['seq'])-steps]
      bot = BotModel.objects(botToken=self.botToken).first()
      newSchema = []
      if(bot):
        newSchema = bot.schema
      
      for sq in newSeq:
        #print sq
        newSchema = newSchema['items'][sq]
      if newSchema['input'] == 'category' or newSchema['input'] == 'org':
        self.updateUser(chatID,'number','')
        self.updateUser(chatID,'note','')
        self.updateUser(chatID,'cart',[])
        self.updateUser(chatID,'count',0)
        self.updateUser(chatID,'product','')
        self.updateUser(chatID,'type','')
        self.updateUser(chatID,'state',0)
      if newSchema['input'] == 'org':
        self.updateUser(chatID,'org',0)

      self.updateUser(chatID,'seq',newSeq)
      self.skipLevelsIfAvailable(chatID)

    def backToMainMenu(self, chatID):
      self.updateUser(chatID,'state',0)
      self.updateUser(chatID,'number','')
      self.updateUser(chatID,'org',0)
      self.updateUser(chatID,'note','')
      self.updateUser(chatID,'cart',[])
      self.updateUser(chatID,'count',0)
      self.updateUser(chatID,'product','')
      self.updateUser(chatID,'type','')
      self.updateUser(chatID,'currentKeyboard',[])
      self.updateUser(chatID,'seq',[])
      self.updateUser(chatID,'extraParameterResults',{})
      self.updateUser(chatID,'extraParameters',[])

    def backToOrg(self, chatID):
      usr = self.getUser(chatID)
      print usr['seq']
      bot = BotModel.objects(botToken=self.botToken).first()
      self.updateUser(chatID,'extraParameterResults',{})
      self.updateUser(chatID,'extraParameters',[])
      print usr['seq']
      if(bot):
        seq = usr['seq'][:1]
        self.updateUser(chatID,'seq',seq)
    def calcWage(self, chatID):
      usr = self.getUser(chatID)
      wge = 0
      for itm in usr['cart']:
        tempWage = WageModel.objects(productType=itm['productType']).first()
        if tempWage:
          wge += tempWage.value
      wge = min(self.maxWage,wge)
      return wge

    def isAdmin(self,chatID):
      adms = BotAdminModel.objects(userID=chatID).first()
      if not adms:
        print 'admin not found'
        return False
      else:
        admins = BotModel.objects(id=self.id).first().botAdmins
        found = False
        for admin in admins:
          if str(chatID) == str(admin.userID):
            print 'admin is in list'
            return True
        print 'admin not in list'
        return False

    def updateProductList(self, chatID, msg):
      bot = BotModel.objects(botToken=self.botToken).first()
      defaultFund = bot.funds[0]
      prds = []
      errors = u''

      for lne in msg.split('\n'):
        if(lne=='‌'):
          continue
        tempProductDetail = lne.split('-')
        fnd = None
        if(len(tempProductDetail)>1):
          fnd = FundModel.objects(fundID=tempProductDetail[1].strip()).first()
          if not fnd:
            errors += u'صندوق %s در لیست صندوق های درگاه شما نیست. %s به صندوق %s اضافه شد.'%(tempProductDetail[1].strip(),prdName,defaultFund.fundID)
        if not fnd:
          fnd = defaultFund
        prdName = prsnr.normalizer(tempProductDetail[0].strip())
        prd = ProductModel.objects(botID=self.id,name=prdName).first()
        if prd:
          if(not fnd in prd.funds):
            prd.funds.append(fnd)
            prd = prd.save()
            errors += 'صندوق گزینه %s به %s تغییر یافت.\n'%(prdName,fnd.fundID)
          if(prd.disabled == True):
            prd.update(set__disabled=False)
            prd = ProductModel.objects(id=str(prd.id)).first()
            errors += 'گزینه %s فعال شد.\n'%(prdName)
          prds.append(prd)
        else:
          prd = ProductModel(name=prdName,productID=unidecode.unidecode(prdName), funds = [fnd], addressRequired = False,
                        price=0,productType='donate', inputUnit='amount', botID=str(bot.id))
          prd.save()
          bot.products.append(prd)
          prds.append(prd)
          bot = bot.save()
          errors += 'گزینه %s ساخته شد.\n'%(prdName)
      botProducts = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
      for p in botProducts:
        if not p in prds:
          p.update(set__disabled=True)
          errors += 'گزینه %s غیر فعال شد.\n'%(p.name)
      if errors == '':
        errors += u'تغییرات با موفقیت انجام شد.'
      else:
        errors += u'\n\n تغییرات با موفقیت انجام شد.'
      self.sendMsg(chatID, errors, settings.KEYBOARDS['adminModelOption'])
      self.updateUser(chatID,'state',14)
    def makeBill(self, chatID):
      #orgIndex = getUserDetail(chatID,'orgIdx')
      #sendMessage(chatID,staticStrings.pleaseWait)
      tempChatID = self.username + '-' + chatID
      usr = json.loads(rds.get(tempChatID))
      url = 'https://example.ir/v2/%s/funds/%s/bills'%(self.phoneNumber,usr['org'])
      print url
      headers = {
        "access-token": self.apiToken,
      }
      note = ''
      amount = 0
      tempLst = []
      wge = self.calcWage(chatID)
      hasProduct = False
      for itm in usr['cart']:
        amount += int(itm['amount'])
        tempStr = ''
        if itm['product'] == 'donate' or itm['productType'] == 'donate':
          tempStr = itm['note']
        else:
          tempStr = itm['note']%(persianiser(itm['count']))
          hasProduct = True

        for extraItm in itm['extraParameterResults']:
          tempStr += '، '+ extraItm +':'+ itm['extraParameterResults'][extraItm]
        tempLst.append(tempStr)
      note = u' و '.join(tempLst)
      if hasProduct:
        note = u'خرید ' + note

      if len(note) > 100:
        note = note[:97] + u'...'

      amount += wge
      amnt = str(amount)
      payload = [
        {
          'payer_name': usr['name'],
          'payer_number': usr['number'],
          'amount': amount,
          'silent': True,
          'due':(datetime.date.today()).isoformat(),
          'note': note
        }
      ]
      r = requests.post(url, json=payload, headers=headers)
      if r.status_code == 200 or r.status_code == 204:
        res = json.loads(r.text)
        
        url = 'https://example.ir/%s/%s-%s'%(res[0]['fund_id'],res[0]['bill_id'],res[0]['code'])
        
        urlStr = unicodedata.normalize('NFKD', url).encode('utf-8','ignore')
        self.updateUser(chatID,str(res[0]['fund_id'])+'/'+str(res[0]['bill_id'])+'-'+res[0]['code'],False)
        
        fundType = FundModel.objects(fundID=usr['org']).first().fundType
        fundName = FundModel.objects(fundID=usr['org']).first().name
        if fundType == 'verified' or fundType == 'direct':
          msg = '\n'.join(staticStrings.verifiedCreatedSuccessfully)%(fundName,note,humanizeAmount(amount), urlStr)
          if self.username == 'yavaranCharityBot':
            msg = msg.replace(u'«باهمتا»','«Baaham.net»')
          self.sendMsg(chatID, msg,self.mainKeyboard, removeCancelButton = True)
          
        else:
          msg = '\n'.join(staticStrings.genericCreatedSuccessfully)%(fundName,note,humanizeAmount(amount), urlStr,self.accountOwner,humanizeNumber(self.phoneNumber))
          if self.username == 'yavaranCharityBot':
            msg = msg.replace(u'«باهمتا»','«Baaham.net»')
          self.sendMsg(chatID, msg,self.mainKeyboard, removeCancelButton = True)
        logChannelMessageID = None
        adminChannelMessageID = None
        try:
          if usr['address'] and len(usr['address'])>0:

            logChannelRes = self.sendMessage(self.logChannel, staticStrings.channelReportWithAddress%(self.botName.replace(u' ',u'_'),fundName,note,humanizeAmount(amount), usr['name'], humanizeNumber(usr['number']), usr['address'], urlStr),disable_web_page_preview=True)
            adminChannelRes = self.sendMessage(self.adminChannel, staticStrings.channelReportWithAddress%(self.botName.replace(u' ',u'_'),fundName,note,humanizeAmount(amount), usr['name'], humanizeNumber(usr['number']), usr['address'], urlStr),disable_web_page_preview=True)
          else:
            logChannelRes = self.sendMessage(self.logChannel, staticStrings.channelReport%(self.botName.replace(u' ',u'_'),fundName,note,humanizeAmount(amount), usr['name'], humanizeNumber(usr['number']), urlStr),disable_web_page_preview=True)
            adminChannelRes = self.sendMessage(self.adminChannel, staticStrings.channelReport%(self.botName.replace(u' ',u'_'),fundName,note,humanizeAmount(amount), usr['name'], humanizeNumber(usr['number']), urlStr),disable_web_page_preview=True)
          logChannelMessageID = logChannelRes['message_id']
          adminChannelMessageID = adminChannelRes['message_id']
        except Exception as e:
          print 'not sent to channel'
        
        
        
        
        usrModel = UserModel.objects(userID=chatID).first()
        if usrModel:
          print 'user found'
          if not usr['number'] in usrModel.phoneNumbers:
            usrModel.phoneNumbers.append(usr['number'])
            usrModel.save()
          else:
            usrModel.phoneNumbers.remove(usr['number'])
            usrModel.phoneNumbers.append(usr['number'])
            usrModel.save(0)
          if 'address' in usr:
            if not usr['address'] in usrModel.addresses:
              usrModel.phoneNumbers.append(usr['number'])
              usrModel.save()
        else:
          usrModel = UserModel(phoneNumbers=[usr['number']],phoneNumber=usr['number'], name=usr['name'],userID = chatID)
          if 'address' in usr:
            usrModel.addresses = [usr['address']]
          usrModel.save()
          print 'user saved'

        productLst = []
        cartItems = []
        for cartPrd in usr['cart']:
          prd = ProductModel.objects(name=cartPrd['product']).first()
          if prd:
            if 'extraParameters' in cartPrd:
              cartItems.append(CartItemModel(product=prd,quantity=cartPrd['count'],extraParameters=cartPrd['extraParameters']))
            else:
              cartItems.append(CartItemModel(product=prd,quantity=cartPrd['count']))
            productLst.append(prd)
          else:
            print 'product %s not found '%(prd)

        lgModel = LogModel(botID=self.id, purchaseType = usr['productType'], logChannelMessageID = str(logChannelMessageID),
                products = productLst, created = dateutil.parser.parse(res[0]['created']), adminChannelMessageID = str(adminChannelMessageID),
                price = usr['amount'], wage = self.calcWage(chatID), user = usrModel, cart = cartItems,
                status = res[0]['status'], billID = str(res[0]['bill_id']), fundID = str(res[0]['fund_id']) )
        
        self.backToMainMenu(chatID)

        lgModel.save()
        

        
      else:
        print r.status_code
        print r.text
        print '##########################'

    def notifPayedSuccessfully(self, bill, tempLog):
      traceNumStr = unicodedata.normalize('NFKD', persianiser(bill['payment']['trace_num'])).encode('utf-8','ignore')
      noteStr = unicodedata.normalize('NFKD', bill['note']).encode('utf-8','ignore')
      payedDate = getJalaliDateFromISO(bill['payment']['modified'])
      payedDate = unicodedata.normalize('NFKD', payedDate).encode('utf-8','ignore')
      orgNameStr = unicodedata.normalize('NFKD', bill['fund_name']).encode('utf-8','ignore')
      amnt = unicodedata.normalize('NFKD', humanizeAmount(bill['amount'])).encode('utf-8','ignore')


      msg = ('\n'.join(staticStrings.payedSuccessfully))%(orgNameStr, noteStr,amnt,payedDate,traceNumStr)
      if self.username == 'yavaranCharityBot':
        msg = msg.replace(u'«باهمتا»','«Baaham.net»')
      self.sendMsg(tempLog.user.userID , msg, useLastKeyboard=True)

      addressRequired = False
      for item in tempLog.cart:
        if(item.product.addressRequired == True):
          addressRequired = True
          break

      admins = BotModel.objects(id=self.id).first().botAdmins
      for admin in admins:
        try:
          if not addressRequired:
            print 'without address'
            self.sendMessage(admin.userID, ('\n'.join(staticStrings.adminChannelReportWithoutAddress))%(noteStr, amnt, tempLog.user.name, humanizeNumber(tempLog.user.phoneNumber)),disable_web_page_preview=True)
          else:
            self.sendMessage(admin.userID, ('\n'.join(staticStrings.adminChannelReport))%(noteStr, amnt, tempLog.user.name, humanizeNumber(tempLog.user.phoneNumber), tempLog.user.address),disable_web_page_preview=True)
        except Exception as e:
          print 'We have no permission to send message to %s'%(admin.userID)
          
        
      try:
        if self.logChannel:
          self.sendMessage(self.logChannel, staticStrings.channelPayReport,reply_to_message_id=tempLog.logChannelMessageID,disable_web_page_preview=True)
      except Exception as e:
          print 'We have no permission to send message to logChannel'
      try:
        if self.adminChannel:
          self.sendMessage(self.adminChannel, staticStrings.channelPayReport,reply_to_message_id=tempLog.adminChannelMessageID,disable_web_page_preview=True)
      except Exception as e:
          print 'We have no permission to send message to adminChannel'


    def getStep(self, chatID):
      usr = self.getUser(chatID)
      bot = BotModel.objects(botToken=self.botToken).first()
      if(bot):
        stp = bot.schema
        for sq in usr['seq']:
          if 'items' in stp:
            if sq in stp['items']:
              stp = stp['items'][sq]
            else:
              print 'not found'
          else:
            break
        return stp
      else:
        print "bot not found"
    def getCurrentKeyboard(self, chatID):
      usr = self.getUser(chatID)
      stp = self.getStep(chatID)
      lst = []
      keybrd = []
      for itm in stp['items']:
        lst.append(itm)
      for l in reversed(lst):
        keybrd.append([l])
      return keybrd
    def sendGetNumberMsg(self, chatID):
      keybrd = []
      keybrd.append([{'text':u'شماره من را ارسال کن','request_contact':True}])
      show_keyboard = {'keyboard': keybrd , 'resize_keyboard':True}
      res = staticStrings.getNumber
      res += '\n\n/cancel'
      self.sendMessage(chatID, res, reply_markup=show_keyboard,disable_web_page_preview=True)
      self.updateUser(chatID,'currentKeyboard',keybrd)
    def sendMsg(self, chatID,msg,keybrd=[],useLastKeyboard = False,removeCancelButton = False):
      usr = self.getUser(chatID)
      res = ''
      if type(msg) is str or type(msg) is unicode:
        res = msg
      else:
        res = '\n'.join(msg)

      if len(keybrd) == 0:
        show_keyboard = hide_keyboard
      else:
        show_keyboard = {'keyboard': keybrd , 'resize_keyboard':True}
      if(len(usr['seq'])>0 and removeCancelButton == False):
        if res.find('\n\n/cancel') == -1:
          res += '\n\n/cancel'
      if(useLastKeyboard):
        self.sendMessage(chatID, res, disable_web_page_preview=True)
      else:
        self.sendMessage(chatID, res, reply_markup=show_keyboard, disable_web_page_preview=True)
      self.updateUser(chatID,'currentKeyboard',keybrd)

    def showCategoryProducts(self, chatID):
      usr = self.getUser(chatID)
      print '###showCategoryProducts'
      print usr['category']
      cat = CategoryModel.objects(id=usr['category']).first()
      print cat.name
      prds = ProductModel.objects(categories=cat,botID=self.id, disabled=False).all()
      print len(prds)
      if len(prds) == 1 and self.skipSingleProduct:
        showMsg=False
        self.updateUser(chatID,'amount',str(prds[0].price))
        if prds[0].productType == 'donate':
          self.updateUser(chatID,'note',prds[0].name)
        else:
          self.updateUser(chatID,'note',u'%s '+ prds[0].name)
        self.updateUser(chatID,'product',prds[0].name)
        self.updateUser(chatID,'productID', str(prds[0].id))
        self.updateUser(chatID,'productType',prds[0].productType)
        self.updateUser(chatID,'state',8)
        self.skipLevelsIfAvailable(chatID)
        self.showProductAmountOptions(chatID)
      else:
        keybrd = []
        for itm in prds:
          if(itm.price > 0):
            keybrd.append([itm.name + ' - ' + humanizeAmount(itm.price)+ u' ﷼'])
          else:
            keybrd.append([itm.name])
        self.sendMsg(chatID,staticStrings.chooseAProduct,keybrd)      


    def showMsg(self,chatID):
      usr = self.getUser(chatID)
      keybrd = []
      stp = self.getStep(chatID)
      showMsg = True
      if 'msg' in stp:
        if 'items' in stp:
          if stp['input'] == 'quantity' or stp['input'] == 'donate':
            for idx in range(0,len(stp['items']),2):
              if idx+1 >= len(stp['items']):
                keybrd.append([stp['items'][idx]])
              else:
                keybrd.append([stp['items'][idx],stp['items'][idx+1]])
          elif stp['input'] == 'org':
            lst = []
            for itm in stp['items']:
              lst.append(itm)
            funds = FundModel.objects(fundID__in=lst).all()
            for fund in funds:
              keybrd.append([fund.name])
          else:
            lst = []
            if 'firstMenu' in stp:
              keybrd = self.mainKeyboard
            else:
              for itm in stp['items']:
                lst.append(itm)
              for l in reversed(lst):
                keybrd.append([l])
        else:
          if stp['input'] == 'product':
            prds = []
            print 'show PRODUCTS'
            if 'category' in usr:
              cat = CategoryModel.objects(id=usr['category']).first()
              prds = ProductModel.objects(categories=cat, disabled=False).all()
            elif 'org' in usr and usr['org']:
              fnd = FundModel.objects(fundID=usr['org']).first()
              prds = ProductModel.objects(funds=fnd, disabled=False).all()
            else:
              prds = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
            lst = []
            botProducts = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
            for p in prds:
              if p in botProducts:
                lst.append(p)
            print lst
            if len(lst) == 1 and self.skipSingleProduct:
              showMsg=False
              if not usr['org'] or usr['org']==0:
                self.updateUser(chatID,'org', str(lst[0].funds[0].fundID))
              self.updateUser(chatID,'amount',str(lst[0].price))
              if lst[0].productType == 'donate':
                self.updateUser(chatID,'note',lst[0].name)
              else:
                self.updateUser(chatID,'note',u'%s '+ lst[0].name)
              self.updateUser(chatID,'product',lst[0].name)
              self.updateUser(chatID,'productID', str(lst[0].id))
              self.updateUser(chatID,'productType',lst[0].productType)
              self.updateUser(chatID,'state',8)
              self.skipLevelsIfAvailable(chatID)
              self.showProductAmountOptions(chatID)
            for itm in lst:
              if(itm.price > 0):
                keybrd.append([itm.name + ' - ' + humanizeAmount(itm.price)+ u' ﷼'])
              else:
                keybrd.append([itm.name])
          elif stp['input'] == 'allCategories':
            if not usr['org'] or usr['org']==0:
              bot = BotModel.objects(botToken=self.botToken).first()
              cats = bot.categories
              categoriesName = []
              for cat in cats:
                categoriesName.append(cat.name)
              print categoriesName
              keybrd = makeTwinKeyboard(categoriesName)
            else:
              fnd = FundModel.objects(fundID=usr['org']).first()
              prds = ProductModel.objects(funds=fnd, botID=self.id, disabled=False).all()
              cats = []
              categoriesName = []
              for prd in prds:
                for ct in prd.categories:
                  if not ct in cats:
                    if ct.botUsername == self.username:
                      cats.append(ct)
              for cat in cats:
                categoriesName.append(cat.name)
              print categoriesName
              keybrd = makeTwinKeyboard(categoriesName)

        if showMsg:
          self.sendMsg(chatID,stp['msg'],keybrd)
        
      elif 'text' in stp:
        if type(stp['text']) is str or type(stp['text']) is unicode:
          self.sendMsg(chatID,stp['text'],self.mainKeyboard)
        else:
          tempStr = '\n'.join(stp['text'])
          self.sendMsg(chatID,tempStr,self.mainKeyboard)
        self.backToMainMenu(chatID)

    def skipLevelsIfAvailable(self, chatID):
      stp = self.getStep(chatID)
      usr = self.getUser(chatID)
      seq = usr['seq']
      tempStr = ''
      while(True):
        if 'text' in stp:
          break
        if stp['input'] == 'org':
          tempStr = stp['items'].keys()[0]
          if('forceMsg' in stp):
            if(stp['forceMsg']):
              self.sendMsg(chatID, stp['msg'])
          self.updateUser(chatID,'org',stp['items'][tempStr]['id'])
        if 'items' in stp:
          if len(stp['items'])==1 and stp['input'] != 'product':
            #print "I could skip %s level"%(stp['input'])
            tempStr = stp['items'].keys()[0]
            stp = stp['items'][tempStr]
            seq.append(tempStr)
          else:
            break
        else:
          break
      self.updateUser(chatID,'seq',seq)

    def finalConfirm(self, chatID):
      tempStr = staticStrings.finalConfirm
      usr = self.getUser(chatID)
      wge = self.calcWage(chatID)
      totalAmount = 0
      for itm in usr['cart']:
        #print itm
        totalAmount += int(itm['amount'])
        if int(itm['count']) > 0:
          tempStr += staticStrings.cartItemSummary%(itm['product'],persianiser(itm['count']),humanizeAmount(itm['amount']))
        else:
          tempStr += staticStrings.cartItemSummaryWithoutCount%(itm['product'],humanizeAmount(itm['amount']))
      if wge > 0:
        tempStr += staticStrings.deliveryPrice%(humanizeAmount(wge))
        totalAmount += wge
      tempStr += '\n' + staticStrings.totalAmount%(humanizeAmount(totalAmount))
      self.sendMsg(chatID,tempStr,settings.KEYBOARDS['addedToCart'])
      self.updateUser(chatID,'state',3)


    def cancelBuy(self, chatID, msg):
      usr = self.getUser(chatID)
      print usr['seq']
      prdType = usr['productType']
      usr = self.initUser(chatID,msg)
      if prdType == 'donate':
        self.sendMsg(chatID,staticStrings.cancelDonate,self.mainKeyboard)
      elif prdType != '':
        self.sendMsg(chatID,staticStrings.cancelBuy,self.mainKeyboard)
      else:
        self.sendMsg(chatID,staticStrings.cancelFunction,self.mainKeyboard)
    
    def getProductQuantity(self, chatID, msg):
      usr = self.getUser(chatID)
      val = convertToDigit(msg)
      validData = False
      if val != '':
        amnt = int(usr['amount'])*int(val)
        if amnt >= 10000 and amnt <= 150000000:
          validData = True
        if validData:
          self.updateUser(chatID,'amount',str(amnt))
          #updateUser(chatID,'note',usr['note']%(persianiser(val)))
          self.updateUser(chatID,'count',val)
          self.updateUser(chatID,'type','product')
          # sendMessage(chatID,staticStrings.addedToCart,settings.KEYBOARDS['addedToCart'])
          self.addToCart(chatID)
          self.updateUser(chatID,'state',1)
          self.finalConfirm(chatID)
          # self.sendGetNumberMsg(chatID)
      if validData == False:
        minVal = persianiser(str(max(1,int(round(10000 / int(usr['amount']))))))
        maxVal = persianiser(str(min(150000000, int(150000000/int(usr['amount'])))))
        self.sendMsg(chatID,staticStrings.productValueRangeError%(minVal,maxVal),useLastKeyboard=True)

    def showProductAmountOptions(self, chatID):
      usr = self.getUser(chatID)
      prd = ProductModel.objects(id=usr['productID']).first()
      if prd.inputType == 'fixed':
        if(len(prd.inputSamples))>1:
          lst = makeTwinKeyboard(prd.inputSamples)
          self.sendMsg(chatID, staticStrings.fixedValue,
                      lst)
        elif len(prd.inputSamples == 1):
          pass
        else:
          self.sendMsg(chatID, staticStrings.runOutText)
      else:
        if(len(prd.inputSamples))>1:
          
          if(prd.inputUnit == 'quantity'):
            lst = makeTwinKeyboard(prd.inputSamples, u' عدد')
            self.sendMsg(chatID, staticStrings.dynamicQuanitityWithSample,
                      lst)
          else:
            lst = makeTwinKeyboard(prd.inputSamples, u' ریال')
            self.sendMsg(chatID, staticStrings.dynamicValueWithSample,
                      lst)
        else:
          if(prd.inputUnit == 'quantity'):
            self.sendMsg(chatID, staticStrings.dynamicQuanitityWithoutSample)
          else:
            self.sendMsg(chatID, staticStrings.dynamicValueWithoutSample)
    def getProductAmount(self, chatID, inpt):
      usr = self.getUser(chatID)
      prd = ProductModel.objects(id=usr['productID']).first()
      val = int(convertToDigit(inpt))
      totalPrice = 0
      print "######################"
      # print prd.inputType
      # print prd.inputUnit
      if prd:
        if prd.inputType == 'fixed':
          print 'FIXED'
          if(inpt in prd.inputSamples):
            if(prd.inputUnit == 'quantity'):
              print "QUANTITY"
              totalPrice = prd.price * val
            else:
              print "NOT QUANTITY"
              totalPrice = val
          else:
            self.sendMsg(chatID,staticStrings.amountInNotRangeText)
            return
        else:
          print 'DYNAMIC'
          if(prd.inputUnit == 'quantity'):
            print "QUANTITY"
            totalPrice = prd.price * val
          else:
            print "NOT QUANTITY"
            totalPrice = val
        print totalPrice
        fundType = FundModel.objects(fundID=usr['org']).first().fundType
        if totalPrice < settings.MIN_VALUE:
          self.sendMsg(chatID,staticStrings.minAmount)
        elif (fundType == 'direct' or fundType == 'generic') and totalPrice > settings.MAX_DIRECT_VALUE:
          self.sendMsg(chatID,staticStrings.maxDirectAmount)
        elif fundType == 'verified' and totalPrice > settings.MAX_VALUE:
          self.sendMsg(chatID,staticStrings.maxVerifiedAmount)
        else:
          if(prd.inputUnit == 'quantity'):
            self.updateUser(chatID,'count',str(val))
          self.updateUser(chatID,'amount',str(totalPrice))
          if len(prd.extraParameters) == 0:
            self.addToCart(chatID)
            if prd.productType == 'donate':
              
              usrModel = UserModel.objects(userID=chatID).first()
              hasNumber = False
              print usrModel
              if usrModel:
                print usrModel.phoneNumbers
                if usrModel.phoneNumbers:
                  hasNumber = True
                  self.updateUser(chatID,'number',usrModel.phoneNumbers[-1])
                  self.validateDetail(chatID)
              if not hasNumber:
                self.updateUser(chatID,'state',1)
                self.sendGetNumberMsg(chatID)
            else:
              self.finalConfirm(chatID)
          else:
            self.updateUser(chatID,'state',13)
            self.updateUser(chatID,'extraParameterResults',{})
            self.updateUser(chatID,'extraParameters',prd.extraParameters)
            self.showExtraParameters(chatID)
      else:
        print "product not found"

    def showExtraParameters(self, chatID, answer=None):
      usr = self.getUser(chatID)
      prd = ProductModel.objects(id=usr['productID']).first()
      
      if(answer != None):
        extraParameter = usr['extraParameters'][0]
        if extraParameter['inputType'] == 'fixed' and not answer in extraParameter['inputSamples']:
          if(len(extraParameter['inputSamples'])>1):
            lst = makeTwinKeyboard(extraParameter['inputSamples'])
            self.sendMsg(chatID, staticStrings.wrongMenuItemError, lst)
          else:
            self.sendMsg(chatID, staticStrings.wrongMenuItemError)
          return
        tempExtraParameters = usr['extraParameterResults']
        tempExtraParameters[extraParameter['title']] = answer
        self.updateUser(chatID,'extraParameterResults',tempExtraParameters)
        self.updateUser(chatID,'extraParameters',usr['extraParameters'][1:])
        usr = self.getUser(chatID)

      if len(usr['extraParameters']) == 0:
        self.addToCart(chatID)
        if prd.productType == 'donate':
          self.updateUser(chatID,'state',1)
          self.sendGetNumberMsg(chatID)
        else:
          self.finalConfirm(chatID)
      else:
        extraParameter = usr['extraParameters'][0]
        if 'inputSamples' in extraParameter:
          # if(len(extraParameter['inputSamples'])>1):
          lst = makeTwinKeyboard(extraParameter['inputSamples'])
          self.sendMsg(chatID, extraParameter['question'], lst)
        else:
          self.sendMsg(chatID, extraParameter['question'])

    def runCurrentStep(self, chatID, msg):
      
      stp = self.getStep(chatID)
      usr = self.getUser(chatID)

      messageText = msg['text']
      #messageText = unicodedata.normalize('NFKD', messageText).encode('utf-8','ignore')
      #print "#########******###########"
      #print msg['text']
      #print stp['input']
      if 'fundID' in stp:
        #print stp['items'].keys()
        found = False
        messageText = stp['fundID']
        funds = BotModel.objects(id=self.id).first().funds
        for fund in funds:
          if fund.fundID == messageText:
            found = True
            fnd = fund
            self.updateUser(chatID,'org',str(fnd.fundID))
            usr['seq'].append(fnd.fundID)
            self.updateUser(chatID,'seq',usr['seq'])
            # print usr['seq']
            #updateUser(chatID,'step',stp['items'][messageText])
            self.skipLevelsIfAvailable(chatID)
            self.showMsg(chatID)
            break
      if stp['input'] == 'menu':
        if messageText in stp['items']:
          #updateUser(chatID,'step',stp['items'][messageText])
          usr['seq'].append(messageText)
          self.updateUser(chatID,'seq',usr['seq'])
          self.skipLevelsIfAvailable(chatID)
          self.showMsg(chatID)
        else:
          self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
      elif stp['input'] == 'category':
        if messageText in stp['items']:
          print messageText
          usr['seq'].append(messageText)
          self.updateUser(chatID,'category',stp['items'][messageText]['id'])
          self.updateUser(chatID,'seq',usr['seq'])
          self.skipLevelsIfAvailable(chatID)
          self.showMsg(chatID)
        else:
          self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
      elif stp['input'] == 'allCategories':
        cat = CategoryModel.objects(name = messageText , botUsername = self.username).first()
        if not cat:
          print 'category not found'
          self.sendMsg(chatID,staticStrings.wrongMenuItemError,usr['currentKeyboard'])
        else:
          self.updateUser(chatID, 'category', str(cat.id))
          self.updateUser(chatID, 'state', 10)
          self.showCategoryProducts(chatID)
      elif stp['input'] == 'org':
        #print stp['items'].keys()
        found = False

        funds = BotModel.objects(id=self.id).first().funds
        for fund in funds:
          if fund.name.strip() == messageText.strip():
            found = True
            fnd = fund
            self.updateUser(chatID,'org',str(fnd.fundID))
            usr['seq'].append(fnd.fundID)
            self.updateUser(chatID,'seq',usr['seq'])
            # print usr['seq']
            #updateUser(chatID,'step',stp['items'][messageText])
            self.skipLevelsIfAvailable(chatID)
            self.showMsg(chatID)
            break
        if found==False:
          print 'not found'
          self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
      elif stp['input'] == 'product':
        prdID = messageText.split(' - ')[0]
        # print BotModel.objects(id=self.id).first()
        prds = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
        #print prds
        print prdID
        productsWithSameName = ProductModel.objects(name=prdID).all()
        if(len(productsWithSameName)==1):
          if(productsWithSameName[0] in prds):
            print '$$$PRODUCT$$$'
            print productsWithSameName[0].name
            print productsWithSameName[0].productType 
            if not usr['org'] or usr['org']==0:
              self.updateUser(chatID,'org', str(productsWithSameName[0].funds[0].fundID))
            self.updateUser(chatID,'amount',str(productsWithSameName[0].price))
            if productsWithSameName[0].productType == 'donate':
              self.updateUser(chatID,'note', prdID)
            else:
              self.updateUser(chatID,'note', u'%s '+ prdID)

            self.updateUser(chatID,'product',prdID)
            self.updateUser(chatID,'productID', str(productsWithSameName[0].id))
            self.updateUser(chatID,'productType',productsWithSameName[0].productType)
            self.updateUser(chatID,'state',8)
            self.skipLevelsIfAvailable(chatID)
            self.showProductAmountOptions(chatID)
          else:
            self.sendMsg(chatID,staticStrings.wrongProductItemError,useLastKeyboard=True)
        else:
          found = False
          for p in productsWithSameName:
            if p in prds:
              found = True
              print '###PRODUCT####'
              print p.name
              print p.productType
              usr['seq'].append(p.productID)
              if not usr['org'] or usr['org']==0:
                self.updateUser(chatID,'org', str(p.funds[0].fundID))
              self.updateUser(chatID,'amount',str(p.price))
              if p.productType == 'donate':
                self.updateUser(chatID,'note', messageText)
              else:
                self.updateUser(chatID,'note', u'%s '+ messageText)
              self.updateUser(chatID,'product',messageText)
              self.updateUser(chatID,'productID', str(p.id))
              self.updateUser(chatID,'productType',p.productType)
              self.updateUser(chatID,'seq',usr['seq'])
              self.skipLevelsIfAvailable(chatID)
              self.showProductAmountOptions(chatID)
              self.updateUser(chatID,'state',8)

              break
          if found == False:
            self.sendMsg(chatID,staticStrings.wrongProductItemError,useLastKeyboard=True)
      elif stp['input'] == 'quantity':
        val = convertToDigit(messageText)
        validData = False
        if val != '':
          amnt = int(usr['amount'])*int(val)
          if amnt >= 10000 and amnt <= 150000000:
            validData = True
          if validData:
            self.updateUser(chatID,'amount',str(amnt))
            self.updateUser(chatID,'state',3)
            self.updateUser(chatID,'count',val)
            self.updateUser(chatID,'type','product')
            self.addToCart(chatID)
            self.finalConfirm(chatID)
        if validData == False:
          minVal = persianiser(str(max(1,int(round(10000 / int(usr['amount']))))))
          maxVal = persianiser(str(min(150000000, int(150000000/int(usr['amount'])))))
          self.sendMsg(chatID,staticStrings.productValueRangeError%(minVal,maxVal),useLastKeyboard=True)

      elif stp['input'] == 'donate':
        print 'donate mode'
        val = convertToDigit(messageText)
        validData = False
        if val != '':
          
          if int(val) >= 10000 and int(val) <= 150000000:
            validData = True
          if validData:
            fundName = None
            if(FundModel.objects(fundID=usr['org']).first()):
              fundName = FundModel.objects(fundID=usr['org']).first().name
            
            if(fundName):
              self.updateUser(chatID,'note',u'پرداخت %s'%(fundName))
            else:
              self.updateUser(chatID,'note',stp['note'])

            self.updateUser(chatID,'amount',val)
            self.updateUser(chatID,'product','donate')
            self.updateUser(chatID,'type','donate')
            self.updateUser(chatID,'productType','donate')
            self.updateUser(chatID,'productID','donate')
            self.updateUser(chatID,'state',1)
            self.addToCart(chatID)
            self.sendGetNumberMsg(chatID)
            
        if validData == False:
          self.sendMsg(chatID,staticStrings.amountValueRangeError,useLastKeyboard=True)

    def addToCart(self, chatID):
      print 'add to cart'
      usr = self.getUser(chatID)
      cart = usr['cart']
      found = False
      for prd in cart:
        if prd['product'] == usr['product'] and prd['extraParameterResults'] == usr['extraParameterResults']:
          found = True
          prd['count'] = int(prd['count']) + int(usr['count'])
          prd['amount'] = int(prd['amount']) + int(usr['amount'])
          break
      if found == False:
        # print usr['extraParameterResults']
        cart.append({'product':usr['product'],'count':usr['count'],'amount':usr['amount'],'extraParameterResults':usr['extraParameterResults'],
                      'note':usr['note'],'productType':usr['productType'],'productID':usr['productID']})
      self.updateUser(chatID,'cart',cart)

    def showProductDetail(self, chatID, prd):
      
      print "show product detail %s"%(prd.name)
      print prd.photo
      print prd.photoID
      res = {}
      messageID = None
      if prd.photo or prd.photoID:
        if prd.photoID:
          print 'send photo from photo ID'
          res = self.sendPhoto(chatID, prd.photoID)
          
        else:
          print 'send photo from data'
          productPhoto = open("%s/%s/%s.jpg"%(TEMPORARY_UPLOAD_FOLDER,self.username,str(prd.id)), 'rb')
          res = self.sendPhoto(chatID, productPhoto)
          photoID = res['photo'][-1]['file_id']
          if photoID:
            prd.photoID = photoID
            prd.save()
        # pprint(res)
        messageID = res['message_id']

      detailStr  = u''
      detailStr += u'نام محصول: %s\n'%(prd.name)
      if prd.url:
        detailStr += u'آدرس صفحه محصول: %s\n'%(prd.url)
      if prd.categories:
        if len(prd.categories)>0:
          lst = []
          for cat in prd.categories:
            lst.append(cat.name)
          detailStr += u'دسته‌بندی: %s\n'%('، '.join(lst))
      detailStr += u'قیمت: %s ﷼\n'%(humanizeAmount(prd.price))
      wge = WageModel.objects(productType=prd.productType).first()
      if wge:
        detailStr += u'هزینه ارسال: %s ﷼\n'%(humanizeAmount(wge.value))
      detailStr += u'آدرس اشتراک گذاری خرید محصول: https://telegram.me/%s?start=%s\n'%(self.username,str(prd.productID))
      
      detailStr += '\n\n/cancel'

      self.updateUser(chatID,'org',str(prd.funds[0].fundID))
      self.updateUser(chatID,'amount',str(prd.price))
      self.updateUser(chatID,'note',u'%s '+ prd.name)
      self.updateUser(chatID,'product',prd.name)
      self.updateUser(chatID,'productID',str(prd.id))
      self.updateUser(chatID,'productType',prd.productType)
      show_keyboard = {'keyboard': settings.KEYBOARDS['directBuy'] , 'resize_keyboard':True}
      if messageID:
        self.sendMessage(chatID, detailStr, reply_to_message_id = messageID,
                      reply_markup=show_keyboard, disable_web_page_preview=True)
      else:
        self.sendMessage(chatID, detailStr, reply_markup=show_keyboard, disable_web_page_preview=True)
    def showProductsList(self, chatID):
      products = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
      lst = []
      for p in products:
        lst.append([p.name + ' - ' + humanizeAmount(p.price)+u' ﷼'])
      self.updateUser(chatID,'state',10)
      self.sendMsg(chatID, staticStrings.chooseAProduct, lst)

    def handle(self, msg):
      flavor = telepot.flavor(msg)
      # print "*****#######******"
      # pprint(msg)
      # print flavor
      # normal message
      if flavor == 'normal' or flavor == 'chat':
        contentType, chatType, chatID = telepot.glance(msg)
        print chatID
        chatID = str(chatID)
        try:
          tempChatID = self.username + '-' + chatID
          usr = json.loads(rds.get(tempChatID))
        except:
          usr = self.initUser(chatID,msg)
          #print msg
        
        if contentType=='text':
          messageText = msg['text']
          if messageText == '/start':
            usr = self.initUser(chatID,msg)
            self.showMsg(chatID)
          elif messageText == '/cancel':
            self.cancelBuy(chatID, msg)
            #sendMessage(chatID,staticStrings.cancelBuy,settings.SCHEMA['mainKeyboard'])
          elif messageText == u'پرداخت' and usr['state'] != 15:
            usr = self.initUser(chatID,msg)
            self.runCurrentStep(chatID,msg)
          elif messageText == '/back':
            self.goBack(chatID)
            self.showMsg(chatID)
          elif messageText == '/product_detail':
            self.showProductsList(chatID)
          elif messageText == '/admin' or messageText == '/Admin':
            if not self.isAdmin(chatID):
              self.sendMsg(chatID, staticStrings.wrongCommandError, useLastKeyboard=True)
            else:
              self.updateUser(chatID,'state',14)
              self.sendMsg(chatID, staticStrings.chooseAnOption, settings.KEYBOARDS['adminModelOption'])
          elif messageText.find('/') == 0:
            if messageText.find('/start') == 0 :
              pid = messageText.split(' ')[1].encode('utf-8')
              if pid.replace(' ','') and pid != 'start':
                productsWithSameID = ProductModel.objects(productID=pid).all()
                selectedPrd = None
                prds = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
                for prd in productsWithSameID:
                  if prd in prds:
                    selectedPrd = prd
                    usr = self.initUser(chatID, msg)
                    self.updateUser(chatID,'state',11)
                    self.showProductDetail(chatID, selectedPrd)
                if selectedPrd == None:
                  self.sendMsg(chatID, staticStrings.badProductIDText)
              else:
                usr = self.initUser(chatID,msg)
                self.showMsg(chatID)
          else:
            if usr['state'] == 0:
              self.runCurrentStep(chatID,msg)
            elif usr['state'] == 1:
              self.validateNumber(chatID, messageText)
            elif usr['state'] == 2:
              if messageText == u'تایید' or messageText == 'yes':
                self.addToCart(chatID)
                self.updateUser(chatID,'state',3)
              else:
                self.cancelBuy(chatID, msg)
                
            elif usr['state'] == 3:
              if messageText == u'افزودن به سبد خرید':

                self.backToOrg(chatID)
                self.skipLevelsIfAvailable(chatID)
                self.updateUser(chatID,'state',0)
                self.showMsg(chatID)
              elif messageText == u'اتمام سفارش و پرداخت':
                self.updateUser(chatID,'state',1)
                self.sendGetNumberMsg(chatID)
              elif messageText == u'رد کردن و شروع مجدد':
                self.cancelBuy(chatID, msg)
                
              else:
                self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
            elif usr['state'] == 4:
              finalizeBuy(chatID)
            elif usr['state'] == 5:
              if messageText == u'تایید':
                self.updateUser(chatID,'state',1)
                self.sendGetNumberMsg(chatID)
              elif messageText == u'رد و شروع مجدد':
                self.cancelBuy(chatID, msg) 
              else:
                self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
            elif usr['state'] == 6:
              if messageText == u'تایید':
                self.makeBill(chatID)
              elif messageText == u'رد و شروع مجدد':
                self.cancelBuy(chatID, msg)
              elif messageText == u'ویرایش تلفن':
                self.updateUser(chatID,'state',1)
                self.sendGetNumberMsg(chatID)
              else:
                self.sendMsg(chatID,staticStrings.wrongMenuItemError,useLastKeyboard=True)
            elif usr['state'] == 7:
              self.getAddress(chatID,messageText)
            elif usr['state'] == 8:
              self.getProductAmount(chatID,messageText)
            elif usr['state'] == 10:
              pid = messageText.split(' - ')[0]
              qryLst = [pid, re.sub(ur'[\W_]+', u'', pid, flags=re.UNICODE),
                        pid.replace(' ','')]
              prds = ProductModel.objects(botID=self.id, disabled=False).order_by('-priority').all()
              found = False
              for p in prds:
                if(p.name in qryLst or p.productID in qryLst):
                  found = True
                  prd = p
                  self.updateUser(chatID,'state',11)
                  self.showProductDetail(chatID, prd)
              if found == False:
                productsWithSameName = ProductModel.objects(name=messageText).all()
                if len(productsWithSameName) == 1:
                  if productsWithSameName[0].productID in prds:
                    prd = productsWithSameName[0]
                    self.updateUser(chatID,'state',11)
                    self.showProductDetail(chatID, prd)
                  else:
                    self.sendMsg(chatID, staticStrings.badProductIDText)
                    self.showProductsList(chatID)
                else:
                  found = False
                  for p in productsWithSameName:
                    if(p.productID in prds):
                      self.updateUser(chatID,'state',11)
                      self.showProductDetail(p, prd)
                      found = True
                  if found == False:
                    self.sendMsg(chatID, staticStrings.badProductIDText)
                    self.showProductsList(chatID)
            elif usr['state'] == 11:
              if messageText == u'ادامه خرید':
                self.showProductAmountOptions(chatID)
                self.updateUser(chatID,'state',8)
              elif messageText == u'لغو':
                if len(usr['cart'])==0:
                  self.updateUser(chatID,'org',0)
                self.backToOrg(chatID)
                self.skipLevelsIfAvailable(chatID)
                self.updateUser(chatID,'state',0)
                self.showMsg(chatID)
              else:
                self.sendMsg(chatID,staticStrings.wrongMenuItemError,settings.KEYBOARDS['directBuy'])
            elif usr['state'] == 12:
              self.getProductQuantity(chatID, messageText)
            elif usr['state'] == 13:
              self.showExtraParameters(chatID, messageText)
            elif usr['state'] == 14:
              if not self.isAdmin(chatID):
                usr = self.initUser(chatID, msg)
                self.showMsg(chatID)
              else:
                if not self.isAdmin(chatID):
                  self.sendMsg(chatID, staticStrings.wrongCommandError, useLastKeyboard=True)
                  return
                if messageText == u'ویرایش گزینه های پرداخت':
                  self.sendMsg(chatID, staticStrings.enterYourProductsList)
                  self.updateUser(chatID,'state',15)
                elif messageText == u'بازگشت به منوی اصلی':
                  usr = self.initUser(chatID,msg)
                  self.showMsg(chatID)
                else:
                  self.sendMsg(chatID,staticStrings.wrongMenuItemError,settings.KEYBOARDS['adminModelOption'])
            elif usr['state'] == 15:
              self.updateProductList(chatID, messageText)
            else:
              usr = self.initUser(chatID, msg)
              self.showMsg(chatID)
        elif contentType=='location':
          if usr['state'] == 8:
            getLocation(chatID,msg['location'])
        elif contentType=='contact':
          print '##############################'
          print msg['contact']['phone_number']
          print str(msg['contact']['user_id'])
          print '##############################'
          if usr['state'] == 1:
            self.validateNumber(chatID, msg['contact']['phone_number'])
        # inline query - need `/setinline`
      elif flavor == 'inline_query':
        query_id, from_id, query_string = telepot.glance(msg, flavor=flavor)
        print('Inline Query:', query_id, from_id, query_string)

        def compute_answer():
          # Compose your own answers
          articles = [{'type': 'article',
                                'id': 'abc', 'title': query_string, 'message_text': query_string}]

          return articles

        self._answerer.answer(msg, compute_answer)

        # chosen inline result - need `/setinlinefeedback`
      elif flavor == 'chosen_inline_result':
        result_id, from_id, query_string = telepot.glance(msg, flavor=flavor)
        print('Chosen Inline Result:', result_id, from_id, query_string)

        # Remember the chosen answer to do better next time
      else:
        raise telepot.BadFlavor(msg)


def getBills():
  while True:
    funds = FundModel.objects.all()
    for fund in funds:
      bt = BotModel.objects(funds=fund).first()
      if bt:
        until = fund.until
        if until == None:
          print "empty until"
          until = ''
        else:
          print "full until"

        url = 'https://api.example.ir/v2/%s/funds/%s/bills?since=%s'%(bt.adminPhoneNumber,fund.fundID,until)
        headers = {
          "access-token": bt.apiToken,
        }
        df = requests.get(url, headers=headers)
        print 'bills of fund %s from %s'%(fund.fundID, until)
        if df.status_code == 200:
          res = json.loads(df.text)
          until = res['until']
          rds.set('until',until)
          fund.until = res['until']
          fund.untilDate = dateutil.parser.parse(res['until'])
          fund.save()

          if 'bills' in res:
            bills = []
            for bill in res['bills']:
              tempLog = LogModel.objects(fundID = str(bill['fund_id']), billID = str(bill['bill_id'])).first()
              if tempLog:
                if bill['status'] == 'payed' and tempLog.status != 'payed':
                  print 'an unreaded fund found'
                  print bill
                  tempLog.payID = bill['pay_id']
                  tempLog.status = bill['status']
                  tempLog.save()

                  bots[tempLog.botID]['bot'].notifPayedSuccessfully(bill, tempLog)
                else:
                  tempLog.status = bill['status']
                  tempLog.save()
          else:
            print "nothing bill in diff"
        else:
          print "nothing to do.diff is empty!"
      else:
        print "standalone fund %s"%(fund.fundID)
      print "#################################"
      time.sleep(600)

def getFundsDetail():
  allBots = BotModel.objects.all()
  for bt in allBots:
    url = 'https://api.example.ir/v2/%s/diff'%(bt.adminPhoneNumber)
    headers = {
      "access-token": bt.apiToken,
    }
    df = requests.get(url, headers=headers)
    if df.status_code == 200:
      res = json.loads(df.text)
      if 'funds' in res:
        for fund in res['funds']:
          fnd = FundModel.objects(fundID=str(fund['fund_id'])).first()
          if fnd:
            fnd.name = fund['name']
            fnd.fundType = fund['type']
            fnd.save()
      else:
        print "nothing fund in diff"
    else:
      print "nothing to do.diff is empty!"


app = Flask(__name__)



@app.route('/store/hook/<path:fundID>', methods=['POST'])
def fundHook(fundID):
    global bots
    bills = []
    funds = []
    dta = json.loads(request.data)
    if 'bills' in dta:
      bills = dta['bills']
    if 'funds' in dta:
      funds = dta['funds']

    for bill in bills:
      tempLog = LogModel.objects(fundID = str(bill['fund_id']), billID = str(bill['bill_id'])).first()
      if tempLog:
        if bill['status'] == 'payed' and tempLog.status != 'payed':
          tempLog.payID = bill['pay_id']
          tempLog.status = bill['status']
          tempLog.save()
          print tempLog.botID
          print bots[tempLog.botID]
          bots[tempLog.botID]['bot'].notifPayedSuccessfully(bill, tempLog)
        else:
          tempLog.status = bill['status']
          tempLog.save()
    for fund in funds:
      fnd = FundModel.objects(fundID=str(fund['fund_id'])).first()
      if fnd:
        fnd.fundType = fund['type']
        fnd.name = fund['name']
        fnd.accountOwner = fund['account_owner']
        fnd.save()
    return 'OK'

@app.route('/store/<path:botID>', methods=['GET', 'POST'])
def pass_update(botID):
    print botID
    if botID in bots:
      print request.data
      print bots[botID]['bot'].username
      print '############################'
      bots[botID]['dataQueue'].put(request.data)  # dump data to queue
    else:
      time.sleep(3)
      if botID in bots:
        bots[botID]['dataQueue'].put(request.data)  # dump data to queue
      else:
        print '##### Bot Not Found #####'
    return 'OK'

# 
# diffThrd = Thread(target=getFundsDetail)
# diffThrd.daemon = True
# diffThrd.start()
allBots = BotModel.objects.all()
for bt in allBots:
  if bt.blocked == False:
    print "init bot"
    bots[str(bt.id)] = {'bot':'', 'dataQueue':Queue()}
    tempBot = StoreBot(bt.botToken)
    bots[str(bt.id)]['bot'] = tempBot
    tempBot.setWebhook(settings.URL+str(bt.id))
    print settings.URL+str(bt.id)
    print "set webHook"
    tempBot.message_loop(source=bots[str(bt.id)]['dataQueue'])
    # thrd = Thread(target=getBills)
    # thrd.daemon = True
    # thrd.start()
print bots
print('Listening ...')
if __name__ == '__main__':
  app.run(port=settings.FLASK_PORT, debug=True)
