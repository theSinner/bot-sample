from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField,\
    StringField, DateTimeField, ReferenceField, FloatField, IntField,\
    EmailField, BooleanField, DictField, URLField, ListField, GeoPointField

class WebModel(Document):
	subDomain = StringField(required=True, unique=True)
	bot = ReferenceField('BotModel', required=True)
	title = StringField()
	logo = StringField()
	backgroundPhoto = StringField()
	about = StringField()
	phoneNumber = StringField()
	address = StringField()
	socialNetworks = DictField()
class CategoryModel(Document):
	name = StringField(required=True, unique=True)
	botUsername = StringField(required=True)

class BotAdminModel(Document):
	userID = StringField(required=True,unique=True)
	phoneNumber = StringField()
class ProductModel(Document):
	name = StringField(required=True)
	botID = StringField()
	productID = StringField(required=True)
	photo = StringField()
	photoID = StringField()
	url = URLField()
	categories = ListField(ReferenceField(CategoryModel))
	priority = IntField(default=0)
	price = IntField(required=True)
	productType = StringField(required=True)
	minQuantities = IntField(default=0)
	maxQuantities = IntField(default=120000000)
	funds = ListField(ReferenceField('FundModel'))
	inputType = StringField(default='dynamic')
	inputSamples = ListField(StringField())
	inputUnit = StringField(default='quantity')
	addressRequired = BooleanField(default=True)
	extraParameters = ListField(DictField())
	disabled = BooleanField(default=False)

class UserModel(Document):
	phoneNumber = StringField()
	phoneNumbers = ListField(StringField(),required=True)
	name = StringField(required=True)
	address = StringField()
	addresses = ListField(StringField())
	publicData = BooleanField(default=False)
	chatIDs = DictField()
	userID = StringField(required=True)

class CartItemModel(EmbeddedDocument):
	quantity = IntField(required=True)
	extraParameters = DictField()
	product = ReferenceField(ProductModel)

class LogModel(Document):
	botID = StringField(required=True)
	purchaseType = StringField(required=True)
	products = ListField(ReferenceField(ProductModel))
	created = DateTimeField(required=True)
	price = IntField(required=True)
	wage = IntField(required=True)
	user = ReferenceField(UserModel)
	payID = IntField()
	billID = StringField(required=True)
	fundID = StringField(required=True)
	status = StringField(required=True)
	logChannelMessageID = StringField()
	adminChannelMessageID = StringField()
	cart = ListField(EmbeddedDocumentField(CartItemModel))

class FundModel(Document):
	fundID = StringField(required=True,unique=True)
	name = StringField(required=True)
	fundType = StringField(required=True)
	until = StringField()
	untilDate = DateTimeField()
	accountOwner = StringField()

class WageModel(Document):
	productType = StringField(required=True,unique=True)
	value = IntField(required=True)


class BotModel(Document):
	name = StringField(required=True,unique=True)
	username = StringField(required=True)
	adminLogChannel = StringField()
	sysLogChannel = StringField()
	botToken = StringField(required=True)
	apiToken = StringField(required=True)
	fundID = StringField(required=True)
	skipSingleProduct = BooleanField(default=False)
	postalCodeRequired = BooleanField(default=True)
	donateMode = BooleanField(default=False)
	adminPhoneNumber = StringField()
	accountOwner = StringField()
	categories = ListField(ReferenceField(CategoryModel))
	schema = DictField(required=True)
	maxWage = IntField(default=0)
	sampleKeyboard = BooleanField(default=False)
	products = ListField(ReferenceField(ProductModel))
	botAdmins = ListField(ReferenceField(BotAdminModel))
	wages = ListField(ReferenceField(WageModel))
	funds = ListField(ReferenceField(FundModel))
	blocked = BooleanField(default=False)
