# Airiq Token Generation Script

import base64

# credentials_string = "AGENTID*MOBILE:PASSWORD"
credentials_string = "AQAG059928*9218077408:9218077408"
encoded_bytes = base64.b64encode(credentials_string.encode("utf-8"))
base64_string = encoded_bytes.decode("utf-8")

print(base64_string)

# Example SSH command to connect to a remote server with port forwarding
cmd = "ssh -L 8888:localhost:8888 ubuntu@13.50.52.0 -i your-key.pem"
