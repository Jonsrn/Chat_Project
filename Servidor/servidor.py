import socket
import threading
import os
import json
import time

# Configuração do servidor
HOST = '127.0.0.1'
PORT = 12345
clientes = {}
cliente_status_file = "clientes_registrados.txt"
palavras_proibidas = ["Tomate Cru", "Mexilhões", "Molho Tartaro", "Faz o L", "Xandao"]
strikes = {}
strike_timer = {}
STRIKE_LIMIT = 3
STRIKE_TIME_LIMIT = 60  # em segundos

def register_mac(mac_id):
    if not os.path.exists(cliente_status_file):
        with open(cliente_status_file, "w") as file:
            pass

    with open(cliente_status_file, "r") as file:
        if mac_id in file.read():
            return

    with open(cliente_status_file, "a") as file:
        file.write(f"{mac_id} True\n")

def update_client_status(mac_id, status):
    # Atualiza o status do cliente no arquivo
    lines = []
    with open(cliente_status_file, "r") as file:
        lines = file.readlines()

    with open(cliente_status_file, "w") as file:
        for line in lines:
            if line.startswith(mac_id):
                line = f"{mac_id} {status}\n"
            file.write(line)

def send_client_list():
    client_list = [{"mac": mac_id, "name": client_data["name"]} for mac_id, client_data in clientes.items()]
    message = json.dumps({"type": "client_list", "clients": client_list}) + '\n'
    for client_data in clientes.values():
        client_data["conn"].sendall(message.encode())

def handle_client(conn, addr):
    buffer = ''
    mac_id = ''
    name = ''
    
    # Receber o registro de nome e MAC do cliente
    try:
        data = conn.recv(1024).decode()
        buffer += data
        if '\n' in buffer:
            registration, buffer = buffer.split('\n', 1)
            registration_data = json.loads(registration)
            mac_id = registration_data["mac"]
            name = registration_data["name"]
    except Exception as e:
        print(f"Erro ao registrar cliente: {e}")
        conn.close()
        return

    if not mac_id or not name:
        conn.close()
        return

    register_mac(mac_id)
    clientes[mac_id] = {"conn": conn, "name": name}
    strikes[mac_id] = 0
    strike_timer[mac_id] = 0

    # Verificar se o usuário já está banido ao iniciar
    with open(cliente_status_file, "r") as file:
        for line in file:
            if line.startswith(mac_id):
                _, status = line.strip().split()
                if status == "False":
                    strikes[mac_id] = STRIKE_LIMIT  # Marcar como banido
                    break

    print(f"{name} ({mac_id}) conectado a partir de {addr}")

    # Enviar lista de clientes para todos
    send_client_list()

    buffer = ''
    while True:
        try:
            data = conn.recv(1024).decode()
            if not data:
                break
            buffer += data
            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                data_json = json.loads(message)
                if data_json["type"] == "message":
                    dest_mac = data_json["dest"]
                    # Verificar se o usuário está banido
                    if strikes[mac_id] >= STRIKE_LIMIT:
                        # Avisar usuário que ele foi banido
                        ban_message = json.dumps({
                            "type": "ban",
                            "content": "(Servidor): Devido a violações de nossos termos de uso, sua conta foi banida permanentemente."
                        }) + '\n'
                        conn.sendall(ban_message.encode())
                        continue

                    # Verificar por palavras proibidas
                    conteudo_mensagem = data_json["content"]
                    for palavra in palavras_proibidas:
                        if palavra in conteudo_mensagem:
                            strikes[mac_id] += 1
                            if strikes[mac_id] == 1:
                                strike_timer[mac_id] = time.time()  # Começar o contador
                            break
                    else:
                        strikes[mac_id] = 0  # Resetar strikes se nenhuma palavra proibida foi encontrada

                    # Se o contador de strikes estiver ativo, verificar se ainda está dentro do limite de tempo
                    if strikes[mac_id] > 0 and time.time() - strike_timer[mac_id] > STRIKE_TIME_LIMIT:
                        strikes[mac_id] = 0  # Resetar strikes após 1 minuto

                    # Se o usuário for banido
                    if strikes[mac_id] >= STRIKE_LIMIT:
                        update_client_status(mac_id, "False")  # Atualiza o status para banido
                        # Avisar usuário que ele foi banido
                        ban_message = json.dumps({
                            "type": "ban",
                            "content": "(Servidor): Devido a violações de nossos termos de uso, sua conta foi banida permanentemente."
                        }) + '\n'
                        conn.sendall(ban_message.encode())
                        continue

                    # Enviar a mensagem se não houver banimento
                    if dest_mac in clientes and strikes[dest_mac] < STRIKE_LIMIT:  # Verificar se destinatário não está banido
                        msg_to_send = json.dumps({
                            "type": "message",
                            "sender": mac_id,
                            "content": conteudo_mensagem
                        }) + '\n'
                        clientes[dest_mac]["conn"].sendall(msg_to_send.encode())
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
            break

    # Remover cliente desconectado
    conn.close()
    if mac_id in clientes:
        del clientes[mac_id]
    print(f"{name} ({mac_id}) desconectado")

    # Atualizar a lista de clientes e enviar para todos
    send_client_list()

# Configurar e iniciar o servidor
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("Servidor rodando...")

    while True:
        conn, addr = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        client_thread.start()
