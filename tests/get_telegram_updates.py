import urllib.request
import json

token = "8831893690:AAFk_OFe0x15U9_cBUw-5JDnVIoVDd-cPA8"
url = f"https://api.telegram.org/bot{token}/getUpdates"

try:
    req = urllib.request.urlopen(url)
    res = json.loads(req.read().decode('utf-8'))
    
    if not res.get("ok"):
        print("Erro ao consultar a API do Telegram:", res)
    else:
        results = res.get("result", [])
        if not results:
            print("Nenhuma mensagem recente encontrada. Por favor, envie qualquer mensagem para o seu bot no Telegram primeiro e tente novamente.")
        else:
            print("--- Mensagens Recentes Recebidas pelo Bot ---")
            for update in results:
                message = update.get("message", {})
                chat = message.get("chat", {})
                user = message.get("from", {})
                text = message.get("text", "")
                
                chat_id = chat.get("id")
                first_name = user.get("first_name", "Usuário")
                username = user.get("username", "")
                
                print(f"De: {first_name} (@{username}) | Chat ID: {chat_id} | Mensagem: '{text}'")
except Exception as e:
    print("Erro de conexao:", e)
