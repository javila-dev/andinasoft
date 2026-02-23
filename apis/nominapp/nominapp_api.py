import requests, base64, json, datetime, os

DIR = os.path.dirname(os.path.abspath(__file__))

class bearer_token():
    
    def __init__(self):
        self.user = 'jorgeavila@somosandina.co'
        self.api_token = '632e08251a8322c1fc7ae6e7388162ed'
        self.token = None
        self.expires = None
        self._load_token_from_disk()
        if not self._token_is_active():
            self._request_token()
    
    def _load_token_from_disk(self):
        try:
            with open(DIR+'/bearer_token.json') as file:
                data = json.load(file)
            self.token = data.get('token')
            self.expires = data.get('expires')
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            self.token = None
            self.expires = None
    
    def _token_is_active(self):
        if not self.token or not isinstance(self.expires, (int, float)):
            return False
        return datetime.datetime.utcfromtimestamp(self.expires) > datetime.datetime.utcnow()
    
    def _request_token(self):
        url = 'https://api.aleluya.com/v1/sessions'
        header = f'{self.user}:{self.api_token}'.encode('ascii')
        b64_header = base64.b64encode(header)
        auth = b64_header.decode('ascii')
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        }
        response = requests.request("POST", url, headers=headers)
        response.raise_for_status()
        token_cookie = None
        cookie_expires = None
        for cookie in response.cookies:
            # Intentar con el nombre nuevo 'token_prod' primero, luego con 'token' por compatibilidad
            if cookie.name in ['token_prod', 'token']:
                token_cookie = cookie.value
                cookie_expires = cookie.expires
                break
        if token_cookie is None:
            # Agregar más información de debug
            cookie_names = [c.name for c in response.cookies]
            response_body = response.text[:500] if response.text else "No body"
            raise ValueError(
                f"No se pudo obtener el token de autenticación desde Aleluya. "
                f"Status: {response.status_code}, "
                f"Cookies recibidas: {cookie_names}, "
                f"Response: {response_body}"
            )
        if cookie_expires is None:
            cookie_expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=25)).timestamp()
        else:
            cookie_expires = int(cookie_expires)
        data_to_save = response.json()
        data_to_save['token'] = token_cookie
        data_to_save['expires'] = cookie_expires
        with open(DIR+'/bearer_token.json', 'w') as file:
            json.dump(data_to_save, file, indent=4)
        self.token = token_cookie
        self.expires = cookie_expires
    
    def get_token(self):
        return self.token
    
    def get_new_token(self):
        self._request_token()
        return self.token
        
class companies():
    def __init__(self,nit):
        self.nit = nit
        self.token = bearer_token().get_token()
        self.cookies = {"token_prod": self.token}
        
    def get_companie_id(self):
        url = f'https://api.aleluya.com/v1/companies?filter=active'
    
        headers = {
            "Accept": "application/json"
        }
        
        response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        if response.status_code == 401:
            self.token = bearer_token().get_new_token()
            self.cookies = {"token_prod": self.token}
            response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        response.raise_for_status()
        payload = response.json()
        data = payload.get('data')
        if not isinstance(data, list):
            error_payload = payload.get('error') or payload
            raise ValueError(f"No se pudo obtener el listado de empresas: {error_payload}")
            
        id_empresa = buscar_lista_dict(list(data),'id_number',str(self.nit),'id')
        if id_empresa is None:
            raise ValueError(f"No se encontró la empresa con NIT {self.nit} en Aleluya.")
        return id_empresa
        
    
class period():
    
    def __init__(self,nit,year,month,
                fortnight:'Int 1 para primera quincena o 2 para la segunda'):
        self.nit = nit
        self.year = int(year)
        self.month = int(month)
        self.fortnight = fortnight
        self.token = bearer_token().get_token()
        self.cookies = {"token_prod": self.token}
        self.company_id = companies(nit).get_companie_id()
    
    def get_period_id(self):
        url = f'https://api.aleluya.com/v1/{self.company_id}/periods'
        headers = {
            "Accept": "application/json"
        }

        response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        if response.status_code == 401:
            self.token = bearer_token().get_new_token()
            self.cookies = {"token_prod": self.token}
            response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        data = response.json().get('data')
        if self.fortnight == 1: q = '01'
        elif self.fortnight == 2: q = '16'
        initial_day = f'{self.year}-{self.month:02d}-{q}'
        id_period = buscar_lista_dict(list(data),'initial_day',initial_day,'id')
        return id_period
    
    def get_period_values(self):
        period_id = self.get_period_id()
        headers = {
            "Accept": "application/json"
        }
        url = f'https://api.aleluya.com/v1/{self.company_id}/periods/{period_id}?per_page=50'
        response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        if response.status_code == 401:
            self.token = bearer_token().get_new_token()
            self.cookies = {"token_prod": self.token}
            response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        """ print(response.json()) """
        data = response.json().get('data').get('payrolls')
        
        return data
    
    def payroll_file(self):
        company_id = companies(self.nit).get_companie_id()
        period_id = self.get_period_id()
        url = f"https://api.aleluya.com/v1/{company_id}/periods/{period_id}/payroll_summary?data_type=summary"

        headers = {
            "Accept": "application/json"
        }
        response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        if response.status_code == 401:
            self.token = bearer_token().get_new_token()
            self.cookies = {"token_prod": self.token}
            response = requests.request("GET", url, headers=headers, cookies=self.cookies)
            
class payroll_concepts():
    def __init__(self,nit):
        self.nit = companies(nit).get_companie_id()
        self.token = bearer_token().get_token()
        self.cookies = {"token_prod": self.token}
        
    def get_concept_id(self,category):
        url = f"https://api.aleluya.com/v1/{self.nit}/payroll_concepts?category={category}"

        headers = {
            "Accept": "application/json"
        }

        response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        if response.status_code == 401:
            self.token = bearer_token().get_new_token()
            self.cookies = {"token_prod": self.token}
            response = requests.request("GET", url, headers=headers, cookies=self.cookies)
        data = response.json().get('data')
         
        id_concept = buscar_lista_dict(list(data), 'name', 'comisiones', 'id')
        
        return id_concept


def buscar_lista_dict(list_of_dicts,key_to_search,value_to_search,key_to_return):
    for dictionary in list_of_dicts:
        if value_to_search == dictionary.get(key_to_search):
            return dictionary.get(key_to_return)
    return None
