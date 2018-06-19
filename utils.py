hide_keyboard = {'hide_keyboard': True}

englishDigits = ['0', '1', '2', '3', '4',
               '5', '6', '7', '8', '9']

persianDigits = ['۰', '۱', '۲', '۳', '۴',
                 '۵', '۶', '۷', '۸', '۹']

persianiserDict = {'0':u'۰', '1':u'۱', '2':u'۲', '3':u'۳', '4':u'۴',
                   '5':u'۵', '6':u'۶', '7':u'۷', '8':u'۸', '9':u'۹'}

digitConvertorDict = {u'۰':'0', u'۱':'1', u'۲':'2', u'۳':'3', u'۴':'4',
                 u'۵':'5', u'۶':'6', u'۷':'7', u'۸':'8', u'۹':'9'}

arabicDigitConvertorDict = {u'٠':'0', u'١':'1', u'٢':'2', u'٣':'3', u'٤':'4',
                 u'٥':'5', u'٦':'6', u'٧':'7', u'٨':'8', u'٩':'9'}

def makeTwinKeyboard(lst, postfix = None):
  res = []
  for idx in range(0,len(lst),2):
    if idx+1 >= len(lst):
      if postfix:
        res.append([str(lst[idx])+postfix])
      else:
        res.append([lst[idx]])
    else:
      if postfix:
        res.append([str(lst[idx])+postfix,str(lst[idx+1])+postfix])
      else:
        res.append([lst[idx],lst[idx+1]])
  return res
def humanizeNumber(num):
  return '0'+num[2:]
def humanizeAmount(amount):
  res = amount
  res = locale.format("%d", int(amount), grouping=True)
  res = persianiser(res)
  res = res.replace(',',u'٬')
  return res
def persianiser(inputStr):
  inputStr = str(inputStr)
  res = ''
  for lttr in inputStr:
    if lttr in persianiserDict:
      res += persianiserDict[lttr]
    else:
      res += lttr
  return res
def convertToDigit(inputStr):
  inputStr = unicodedata.normalize('NFKD', inputStr).encode('utf-8','ignore')
  inputStr = inputStr.decode('utf8')
  res = ''
  for lttr in inputStr:
    if lttr in digitConvertorDict:
      res += digitConvertorDict[lttr]
    elif lttr in arabicDigitConvertorDict:
      res += arabicDigitConvertorDict[lttr]
    elif lttr in englishDigits:
      res += lttr
  return res

def getJalaliDateFromISO(isoDate):
  dt = datetime.datetime.strptime(isoDate, '%Y-%m-%dT%H:%M:%S.%fZ')
  dt = dt.replace(tzinfo=from_zone)
  dt = dt.astimezone(to_zone)
  jl = JalaliDatetime(dt)
  jlStr = jl.strftime('%N/%R/%D %k:%r:%s')
  return jlStr
      

def getPaymentDetail(pay_id,payments):
  for pay in payments:
    if(pay['pay_id'] == pay_id):
      dt = datetime.datetime.strptime(pay['created'], '%Y-%m-%dT%H:%M:%S.%fZ')
      dt = dt.replace(tzinfo=from_zone)
      dt = dt.astimezone(to_zone)
      jl = JalaliDatetime(dt)
      jlStr = jl.strftime('%N/%R/%D %k:%r:%s')
      return [pay['trace_num'], jlStr]

