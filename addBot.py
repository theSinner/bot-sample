# This Python file uses the following encoding: utf-8
from mongoengine import *
from settings import *
from pymongo import read_preferences
from models import *

connect(MONGO_DATABASE,read_preference=read_preferences.ReadPreference.PRIMARY ,host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USERNAME, password=MONGO_PASSWORD)

SCHEMA = {
	'mainKeyboard' : [[u'Pay'], [u'About us']],
	'msg': 'Welcome to the bot',
	'input':'menu',
	'items':{
		u'Pay':{
			'msg': 'Please choose one:',
			'input':'product',
		},
		u'About us':{
			'text': '  ‌‌‌‌  '
		}
	}
}


BOT_NAME = u'the Bot'
USERNAME = 'theBot'
BOT_TOKEN = 'xxxxxxxxxxx:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'
PHONE_NUMBER = 'XXXXXXXXXXX'
TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
LOG_CHANNEL = 'XXXXXXXXXXX'
ADMIN_CHANNEL = 'XXXXXXXXXXX'

ACCOUNT_OWNER = u' ‌'
BOT_NUMBER = 'XXXXXXXXXXX'
MAX_WAGE = 45000

wageLst = []
fundLst = []

fnd = FundModel.objects(fundID='xxxxx').first()
if not fnd:
	fnd = FundModel(fundID='xxxx',name=u'Fund Name',fundType='verified').save()
fundLst.append(fnd)



productLst = []
prd = ProductModel.objects(productID='prd1', funds = fnd).first()
if not prd:
	prd = ProductModel(name=u'Test Item',productID='prd1', funds = [fnd], addressRequired = False,
												price=0,productType='donate', inputUnit='amount')
	prd.save()
productLst.append(prd)





bot = BotModel.objects(username=USERNAME).first()
if not bot:
	bot = BotModel(name=BOT_NAME, username=USERNAME, adminLogChannel=ADMIN_CHANNEL,
							sysLogChannel=LOG_CHANNEL, botToken=BOT_TOKEN, apiToken=TOKEN,
							adminPhoneNumber=PHONE_NUMBER, accountOwner=ACCOUNT_OWNER, schema=SCHEMA,donateMode=True, fundID='5508',
							maxWage=MAX_WAGE, wages=wageLst, funds=fundLst, products=productLst,postalCodeRequired=False,skipSingleProduct=True)
	bot.save()
else:
	bot.schema = SCHEMA
	bot.name = BOT_NAME
	bot.username = USERNAME
	bot.adminLogChannel = ADMIN_CHANNEL
	bot.sysLogChannel = LOG_CHANNEL
	
	for fnd in fundLst:
		if not fnd in bot.funds:
			bot.funds.append(fundLst[fnd])
	
	for wg in wageLst:
		if not wg in bot.wages:
			bot.wages.append(wageLst[wg])

	bot.save()


for prd in bot.products:
	prd.botID = str(bot.id)
	prd.save()

bot.botAdmins = []
admn = BotAdminModel.objects(userID = 'xxxxxxx').first()
if not admn:
		admn = BotAdminModel(userID = 'xxxxxxx').save()

bot.botAdmins.append(admn)


bot.save()
