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
    connected_clients = list(clientes.keys())
    message = json.dumps({"type": "client_list", "clients": connected_clients}) + '\n'
    for client_conn in clientes.values():
        client_conn.sendall(message.encode())

def handle_client(conn, addr):
    mac_id = ''
    buffer = ''
    while True:
        try:
            data = conn.recv(1024).decode()
            if not data:
                break
            buffer += data
            if '\n' in buffer:
                mac_id, buffer = buffer.split('\n', 1)
                break
        except:
            break

    if not mac_id:
        conn.close()
        return

    register_mac(mac_id)
    clientes[mac_id] = conn
    print(f"{mac_id} conectado a partir de {addr}")

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
                        clientes[dest_mac].sendall(msg_to_send.encode())
        except:
            break

    # Remover cliente desconectado
    conn.close()
    if mac_id in clientes:
        del clientes[mac_id]
    print(f"{mac_id} desconectado")

    # Atualizar a lista de clientes e enviar para todos
    send_client_list()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print("Servidor iniciado, aguardando conexões...")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    start_server()
