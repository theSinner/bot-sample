# This Python file uses the following encoding: utf-8

MONGO_HOST = 'localhost'
MONGO_PORT = 27017
MONGO_USERNAME = ''
MONGO_PASSWORD = ''
MONGO_DATABASE = 'store-bot'

URL = 'https://devbot.ajorloo.com/store/'

FLASK_PORT = 8083

MAX_DIRECT_VALUE = 150000000
MAX_VALUE = 500000000
MIN_VALUE = 10000

class PaymentState:
    waiting = 'waiting'
    payed = 'payed'
    rejected = 'rejected'
    reversed = 'reversed'

class DeveliryState:
    inReview = 'inReview'
    delivering = 'delivering'
    delivered = 'delivered'


TEMPORARY_UPLOAD_FOLDER = 'upload'


#ME 166367321

KEYBOARDS = {
	'getLocation' : [[u'ارسال موقعیت جغرافیایی'],[u'اتمام سفارش']],
	'addedToCart' : [[u'اتمام سفارش و پرداخت'],[u'افزودن به سبد خرید'],[u'رد کردن و شروع مجدد']],
	'skipLocation': [[u'اتمام سفارش']],
	'confirmItem' : [[u'تایید'],[u'رد و شروع مجدد',u'ویرایش تلفن']],
	'finalConfirm' : [[u'تایید',u'رد و شروع مجدد']],
	'directBuy' : [[u'ادامه خرید',u'لغو']],
	'numberOfProduct': [[u'۱ عدد',u'۲ عدد'],[u'۳ عدد',u'۴ عدد'],[u'۵ عدد']],
	'adminModelOption': [[u'ویرایش گزینه های پرداخت'],[u'بازگشت به منوی اصلی']]
}


