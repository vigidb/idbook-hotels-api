import base64

# credentials_string = "AGENTID*MOBILE:PASSWORD"
credentials_string = "AQAG059928*9218077408:9218077408"
encoded_bytes = base64.b64encode(credentials_string.encode('utf-8'))
base64_string = encoded_bytes.decode('utf-8')

print(base64_string)
