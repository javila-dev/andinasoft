from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import requests
import json
import os

ACCESS_KEY = 'NGZlNmQ1N2YtNTczZi00MmNkLTk2OGQtOTA2N2FhY2MwMjZmOmhxazYwaC80PEc=' # Produccion
#ACCESS_KEY ='OWE1OGNkY2QtZGY4ZC00Nzg1LThlZGYtNmExMzUzMmE4Yzc1OldxLjcwZldMOFc=' # Pruebas
USERNAME = 'contabilidad3@somosandina.co'# Produccion
#USERNAME = 'siigoapi@pruebas.com'# Pruebas
EXPIRES = datetime.now()

DIR = os.path.dirname(os.path.abspath(__file__))

class SIIGOapi:
    
    def __init__(self,username=USERNAME,access_key=ACCESS_KEY,*args,**kwargs):
        super(SIIGOapi).__init__(*args,**kwargs)
        self.access_key = access_key
        self.username = username
    
    def check_token(self):
        with open(DIR+'/siigoToken.json','r') as file:
            token = json.load(file)
        
        expires = datetime.strptime(token.get('expires'),'%Y-%m-%d %H:%M:%S.%f')
        
        if datetime.utcnow() >= expires:
            return None
        
        return token.get('token')
    
    def generatetoken(self):
        
        valid_token = self.check_token()
        
        if valid_token:
            return valid_token
        
        values = f"""{{
            "username": "{self.username}",
            "access_key": "{self.access_key}"
        }}"""

        headers = {
        'Content-Type': 'application/json'
        }
        
        r = requests.post('https://api.siigo.com/auth', data=values, headers=headers)
        token = r.json().get('access_token')
        expires = datetime.utcnow() + relativedelta(hours=23)
        data = {
            'token':token,
            'expires':f'{expires}'
        }
        
        with open(DIR+'/siigoToken.json','w') as file:
            json.dump(data, file, indent=4)
        
        
        return token
    
    def get_documents_types(self,document_type):
        """
        Consulta la lista de documentos segun el tipo solicitado.
        
        Parameters:
            document_type (str): el tipo de docuemtno a consultar FV/NC/RC
        
        Returns:
            list: Regresa una lista de diccionarios con todos los documentos creados en Siigo nube del tipo solicitado. 
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        r = requests.get(f'https://api.siigo.com/v1/document-types?type={document_type}',headers=headers)
        
        document_types = r.json()
        
        return document_types
        
    def create_partner(self,document_type,document_id,first_name,last_name,fiscal_responsabilities:list,
                      address,country,state,city,phone,email,user,type_of_partner='Customer'):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        phone = phone.replace('-','')
        if phone.include('('):
            phone = phone.split(' ')[1]
        
        if document_id == 31:
            name = f'["{first_name} {last_name}"]'  
            person_type = 'Company'
        else:
            name = f'["{first_name}","{last_name}"]'
            person_type = 'Person'
        
        fr_list = ""
        for fr in fiscal_responsabilities:
            fr_list += f"""
            {{
                "code":"{fr}"
            }},
            """
        
        values = f"""
                {{
                    "type": "{type_of_partner}",
                    "person_type": "{person_type}",
                    "id_type": "{document_type}",
                    "identification": "{document_id}",
                    "name": {name},
                    "branch_office": 0,
                    "active": true,
                    "vat_responsible": false,
                    "fiscal_responsibilities": [
                        {fr_list}
                    ],
                    "address": {{
                        "address": "{address[:36]}",
                        "city": {{
                            "country_code": "{country}",
                            "state_code": "{state}",
                            "city_code": "{city}"
                        }},
                    }},
                    "phones": [
                        {{
                            "number": "{phone}",
                        }}
                    ],
                    "contacts": [
                        {{
                            "first_name": "{first_name}",
                            "last_name": "{last_name}",
                            "email": "{email}",
                            "phone": {{
                                "number": "{phone}",
                            }}
                        }}
                    ],
                    "comments": "Cliente creado desde AlttumSoft por {user}",
                }}
                """
        
        r = requests.post('https://api.siigo.com/v1/customers', data=values, headers=headers)
        
        
        return r.json()
    
    def get_partners(self,next_link=None):
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        href = 'https://api.siigo.com/v1/customers'
        if next_link: href = next_link
        
        r = requests.get(href,headers=headers)
        
        clients = r.json()
        
        return clients
    
    def get_payment_types(self,document_type:str):
        '''
        Parameters:
            document_type (str)
        '''
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        r = requests.get(f'https://api.siigo.com/v1/payment-types?document_type={document_type}',headers=headers)
        
        return r.json()
        
    def get_taxes(self):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        r = requests.get('https://api.siigo.com/v1/taxes',headers=headers)
        
        taxes = r.json()
        
        return taxes
    
    def get_cost_center(self):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        r = requests.get('https://api.siigo.com/v1/cost-centers',headers=headers)
        
        cost_center = r.json()
        
        return cost_center
    
    def get_product(self,code):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        href = f'https://api.siigo.com/v1/products?code={code}'

        r = requests.get(href,headers=headers)
        
        product = r.json()
        
        return product

    def get_products(self,next_page=None):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        href = 'https://api.siigo.com/v1/products'
        if next_page: href = next_page
        r = requests.get(href,headers=headers)
        
        products = r.json()
        
        return products
    
    def get_users(self,next_page=None):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        href = 'https://api.siigo.com/v1/users'
        if next_page: href = next_page
        r = requests.get(href,headers=headers)
        
        users = r.json()
        
        return users
    
    def create_FV(self, document_id:int,date:str,customer_id:int,seller:int,observations:str,
                  items:list,payments:list,cost_center="",
                  advance_payment=0):
        """
        Los parametros que incluyen id, se refieren al id propio de siigo
        
        Parameters:
            date: en formato %Y-%m-%d
            items: una lista de diccionarios que debe contener \n 
                {"code":str,
                "description":str,
                "quanty":int,
                "price":float,
                "taxes":[
                    {{"id":int}}
                    ]
                }
            payments: una lista de diccionarios que debe contener \n 
                [{
                "id": int,
                "value": float,
                "due_date": "2022-09-10"
                },
            
        Returns:
            siigo id para la factura de venta creada
        
        """
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        values = f"""
                {{
                "document": {{
                    "id": {document_id}
                }},
                "date": "{date}",
                "customer": {{
                    "identification": "{customer_id}",
                }},
                "cost_center": {cost_center},
                "seller": {seller},
                "observations": "{observations}",
                "items": {items},
                "payments": {payments},
                }}
                """

        r = requests.post('https://api.siigo.com/v1/invoices',headers=headers,data=values)
        
        invoice = r.json()
        
        return invoice
    
    def create_AdvanceRC(self,document_id:int,date:str,customer_id:int,
                         payment_id:int,value:int, observations:str):
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        
        values = f"""
            {{
                "document": {{
                    "id": {document_id}
                }},
                "date": "{date}",
                "type": "AdvancePayment",
                "customer": {{
                    "identification": "{customer_id}",
                    "branch_office": 0
                    }},
                "payment": {{
                    "id": {payment_id},
                    "value": {value}
                    }},
                "observations": "{observations}"
            }}
            """
        
        r = requests.post('https://api.siigo.com/v1/vouchers',headers=headers,data=values)
        
        vouchers = r.json()
        
        return vouchers
    
    def create_journals(self,document_id:int,date:str,movement:list,observations:str):
        """
        Parameters:
            debit (list): Es una lista de diccionarios con el detalle del comprobante a crear,
            el dict debe tener la siguiente estructura:
                {
                    "account": , #cuenta
                    "movement": , # D/C
                    "costumer_id": , #id_tercero
                    "description": , #descripcion
                    "cost_center": , #centro de costo
                    "value":  ,#valor(float)
                    "due": {
                        "prefix": #"CC-1",
                        "consecutive": #5000,
                        "quote": #1,
                        "date": #"2021-04-22"
                    }
                }
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization':'Bearer '+self.generatetoken()
        }
        items = ""
        for item in movement:
            items += f"""
                {{
                    "account": {{ 
                        "code": "{item.get('account')}",
                        "movement": "{item.get('movement')}"
                    }},
                    "customer": {{
                        "identification": "{item.get('costumer_id')}",
                        "branch_office": 0
                    }},
                    "description": "{item.get('description')}",
                    "cost_center": {item.get('cost_center')},
                    "value": {item.get('value')}
                }},
            """
        
        values = f"""
            {{
                "document": {{
                "id": {document_id}
                }},
                "date": "{date}",
                "items": [
                    {items}
                ],
                "observations": "{observations}"
            }}
            """
            
        r = requests.post('https://api.siigo.com/v1/journals',headers=headers,data=values)
        
        journal = r.json()
        
        return journal
    
#api = SIIGOapi()

#CREAR UN CLIENTE
""" partner = api.create_partner(
    document_type=13, document_id=70952488, 
    first_name= 'RUBEN DE JESUS', last_name='HOYOS QUINCHIA',
    fiscal_responsabilities="R-99-PN", address="Vereda el chilco",
    country="CO",state="05",city="05321", phone="3113937074",
    email="sincorreo@sincorreo.com",user='javila',
    type_of_partner='Supplier'
) """

#Endpoints de GET
#print(api.get_product('HOSPALTT'))
#for r in api.get_cost_center(): print(r)
#print('\n---------------------------\n')
""" for r in api.get_payment_types('FV'): print(r)
print('\n---------------------------\n') """
#for r in api.get_documents_types('FV'): print(r) #----->28245
#print('\n---------------------------\n')#
#for r in api.get_taxes(): print(r)#-------->13171
#print('\n---------------------------\n')
""" result =  api.get_partners()
next = True
while next:
    for r in result.get('results'): 
        print(r)
    if result.get('_links'):
        next_page = result.get('_links').get('next')
        if next_page:
            result =  api.get_partners(next_page.get('href'))
        else: 
            next = False
    else:
        next = False """
        
    #print(r)#--------->86556efa-c443-430b-8bbc-af2d8e6bdc3d
""" result =  api.get_users()
next = True
while next:
    for r in result.get('results'): 
        print(r)
    if result.get('_links'):
        next_page = result.get('_links').get('next')
        if next_page:
            result =  api.get_users(next_page.get('href'))
        else: 
            next = False
    else:
        next = False """
        
""" result =  api.get_products()
next = True
while next:
    for r in result.get('results'): 
        print(r)
    if result.get('_links'):
        next_page = result.get('_links').get('next')
        if next_page:
            result =  api.get_products(next_page.get('href'))
        else: 
            next = False
    else:
        next = False """
        

#CREAR FACTURAS
""" items = [{"code":"CONSUMALTT",
        "description":"CONSUMOS CLUB ALTT",
        "quantity":1, 
        "price":75000.00,
        "taxes":[
            {"id":13171} 
            ]
        },
        {"code":"HOSPALTT",
        "description":"HOSPEDAJE ALTT",
        "quantity":3, 
        "price":90000.00,
        "taxes":[
            {"id":14287} 
            ]
        },
        ]

payments = [{
    "id": 8773,
    "value": 150000.00,
    "due_date": "2022-09-10"
    
    },
    {
        "id": 8581,
        "value": 201000.00,
        "due_date": "2022-09-10"
    }]

FV = api.create_FV(
    document_id=28623,date="2022-09-10",customer_id=73071140,
    seller = 1001, observations= 'FV creada desde Alttumsoft',
    items=items, payments=payments, 
    cost_center = "512",
)

print(FV) """

""" movement = [{
            "account": 51550501, #cuenta
            "movement": "Debit", # Debit/Credit
            "costumer_id": 900842110, #id_tercero
            "description": "PASAJES A CONVENCION DE HOTELES BAQ", #descripcion
            "cost_center": "", #centro de costo
            "value": 423582 #valor(float)
        },
        {
            "account": 51550501, #cuenta
            "movement": "Debit", # D/C
            "costumer_id": 900749192, #id_tercero
            "description": "ARREGO DE COCINA, FUGA DE GAS", #descripcion
            "cost_center": "", #centro de costo
            "value": 250000#valor(float)
        },
        {
            "account": 22050501, #cuenta
            "movement": "Credit", # D/C
            "costumer_id": 52930191, #id_tercero
            "description": "CXP GASTOS CAJA MENOR 01/09/22 AL 05/09/22", #descripcion
            "cost_center": "", #centro de costo
            "value": 673582,#valor(float),
            "due": {
                
            }
        },
            ]

JL = api.create_journals(
    document_id=24472, date = "2022-09-05",
    movement = movement, observations= 'Legalizacion de caja menor de Fulanito de tal',
)

print(JL) """
""" RC = api.create_AdvanceRC(document_id=28629,date="2022-09-10",customer_id=73071140,
                     payment_id=5638,value=150000,
                     observations='Anticipo por reserva de 2 dias en Alttum Venecia')
print(RC) """