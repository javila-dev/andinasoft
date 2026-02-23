
import requests

class Dlocal():

    def __init__(self):
        self.apikey = 'wMfUTZOkbqnGZJoAxkqagvwVVsBRiSpZ'
        self.secretkey = '6jnHbkE1ASHGrn9d8GlEOiJOfC7pDnbGoGOiQi8x'
        

    def APIcall(self, url, data):
        header = f'{self.apikey}:{self.secretkey}'
        headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {header}",
            }
        response = requests.request("POST", url, headers=headers, json=data)
        
        return response.json()
    
    def createpayment(self,amount,contrato,country='CO',currency = 'COP'):
        data = {
            'currency': currency,
            'amount': amount,
            'country': country,
            'description': f'Abono contrato Fractal No {contrato}',
            'expiration_type':"DAYS",
            'expiration_value':5
        }
        url = "https://api.dlocalgo.com/v1/payments"
        
        response = self.APIcall(url, data)
        
        return response.get('redirect_url')


