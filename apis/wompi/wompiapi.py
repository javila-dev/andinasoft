import json
import secrets
import requests



class wompi_payments:
    
    def __init__(self,proyecto):
        self.domain = 'https://production.wompi.co/v1'
        empresa = {
            'Sandville Beach': 900993044,
            'Perla del Mar': 900993044,
            'Carmelo Reservado': 900993044,
            'Tesoro Escondido':901018375,
            'Vegas de Venecia':901018375,
        }
        pb_k = ''
        pv_k = ''
        if empresa[proyecto] == 901018375:
            pb_k = 'pub_prod_iK7zudCg9gi72JmpTImdLMI2uX2y0FMV'
            pv_k = 'prv_prod_gxpJ5CyXl2IjT9AhSW38Oozx2cqUEUdk'
        elif empresa[proyecto] == 900993044:
            pb_k = 'pub_prod_4Xmi92dLk5aziPacWMe4gGZCCGTUfFSZ'
            pv_k = 'prv_prod_PunzCK5p5QM5CRYPflbmEOTdHKQfvhPA'
            
        self.pb_k = pb_k
        self.pv_k = pv_k
        
    def get_accept_token(self):
        url = f'{self.domain}/merchants/{self.pb_k}'
    
        response = requests.request("GET", url)
        token = response.json().get('data').get('presigned_acceptance').get('acceptance_token')
        
        return token
        
    def create_payment_source(self,email,p_type,token):
        accept_token = self.get_accept_token()
        url = f'{self.domain}/payment_sources'
    
        headers = {
            "accept": "application/json",
            'Content-Type': 'application/json',
            "Authorization": f'Bearer {self.pv_k}'
        }
        data = {
            "type": p_type,
            "token": token,
            "customer_email": email,
            "acceptance_token": accept_token
        }
        
        data = json.dumps(data)
        
        response = requests.request("POST", url, headers=headers,data=data)
        
        data = response.json().get('data')
        
        return data
    
    def create_transaction(self,pay_source_id,ammount,email,installments):
        
        url = f'{self.domain}/transactions'
        reference = secrets.token_hex(16)
        ref_in_bd = wompi_transactions.objects.filter(reference=reference)
        
        while ref_in_bd.exists():
            reference = secrets.token_hex(16)
            ref_in_bd = wompi_transactions.objects.filter(reference=reference)
        
        
        headers = {
            "accept": "application/json",
            'Content-Type': 'application/json',
            "Authorization": f'Bearer {self.pv_k}'
        }
        data = {
            "amount_in_cents": ammount, 
            "currency": "COP", 
            "customer_email": email,
            "payment_method": {
                "installments": installments
            },
            "reference": reference,
            "payment_source_id": pay_source_id
        }
        
                    
        data = json.dumps(data)
        
        response = requests.request("POST", url, headers=headers,data=data)
        
        data = response.json().get('data')
        
        return reference
