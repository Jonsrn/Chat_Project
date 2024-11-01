import socket
import threading
import os
import json

# Configuração do servidor
HOST = '127.0.0.1'
PORT = 12345
clientes = {}
cliente_status_file = "clientes_registrados.txt"

def register_mac(mac_id):
    if not os.path.exists(cliente_status_file):
        with open(cliente_status_file, "w") as file:
            pass

    with open(cliente_status_file, "r") as file:
        if mac_id in file.read():
            return

    with open(cliente_status_file, "a") as file:
        file.write(f"{mac_id} True\n")

def send_client_list():
    # Enviar a lista de clientes conectados para todos os clientes
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
                    if dest_mac in clientes:
                        msg_to_send = json.dumps({
                            "type": "message",
                            "sender": mac_id,
                            "content": data_json["content"]
                        }) + '\n'
                        clientes[dest_mac]["conn"].sendall(msg_to_send.encode())
        except:
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
