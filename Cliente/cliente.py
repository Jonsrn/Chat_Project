import sys
import os
import random
import socket
import threading
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QListWidget, QComboBox, QTextEdit, QInputDialog
from PyQt5.QtCore import Qt

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat - Cliente")
        self.setGeometry(100, 100, 600, 500)
        
        self.mac_id = self.load_or_generate_mac()
        self.user_name = self.load_or_request_name()
        self.message_history_file = f"{self.mac_id}_history.txt"
        self.nome_para_mac = {}

        # Conectar ao servidor
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('127.0.0.1', 12345))
        self.client_socket.sendall((json.dumps({"type": "register", "mac": self.mac_id, "name": self.user_name}) + '\n').encode())
        
        # Criar a interface
        self.initUI()
        self.load_message_history()

        # Thread para receber mensagens continuamente
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def initUI(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # Área de lista de clientes
        left_layout = QVBoxLayout()
        client_label = QLabel("Usuários Online:")
        client_label.setAlignment(Qt.AlignCenter)
        self.client_list_widget = QListWidget()
        left_layout.addWidget(client_label)
        left_layout.addWidget(self.client_list_widget)
        main_layout.addLayout(left_layout, 1)

        # Área de mensagens e entrada
        right_layout = QVBoxLayout()

        # Área de exibição das mensagens
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        right_layout.addWidget(self.message_display, 4)

        # Selecionar destinatário
        dest_layout = QHBoxLayout()
        dest_label = QLabel("Enviar para:")
        self.dest_selector = QComboBox()
        dest_layout.addWidget(dest_label)
        dest_layout.addWidget(self.dest_selector)
        right_layout.addLayout(dest_layout)

        # Entrada de mensagem
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Digite sua mensagem...")
        right_layout.addWidget(self.message_input)

        # Botão de enviar
        send_button = QPushButton("Enviar")
        send_button.clicked.connect(self.send_message)
        right_layout.addWidget(send_button)

        main_layout.addLayout(right_layout, 3)

        self.setCentralWidget(main_widget)

    def load_or_generate_mac(self):
        mac_file = "mac_address.txt"
        if os.path.exists(mac_file):
            with open(mac_file, "r") as file:
                return file.read().strip()
        
        mac_id = f"{random.randint(1000, 9999)}"
        with open(mac_file, "w") as file:
            file.write(mac_id)
        return mac_id

    def load_or_request_name(self):
        name_file = "user_name.txt"
        if os.path.exists(name_file):
            with open(name_file, "r") as file:
                return file.read().strip()
        
        name, ok = QInputDialog.getText(self, "Nome de Usuário", "Digite seu nome:")
        if ok and name:
            with open(name_file, "w") as file:
                file.write(name)
            return name
        return "Usuário"

    def load_message_history(self):
        if os.path.exists(self.message_history_file):
            with open(self.message_history_file, "r") as file:
                for line in file:
                    self.display_message(line.strip(), False)

    def save_message(self, message):
        with open(self.message_history_file, "a") as file:
            file.write(message + "\n")

    def send_message(self):
        message = self.message_input.text()
        dest_name = self.dest_selector.currentText()
        dest_mac = self.nome_para_mac.get(dest_name, "")
        
        if message and dest_mac:
            display_text = f"Você: {message}"
            self.display_message(display_text, True)
            self.save_message(display_text)
            
            # Formata e envia a mensagem como JSON para o servidor
            data = json.dumps({"type": "message", "dest": dest_mac, "content": message}) + '\n'
            self.client_socket.sendall(data.encode())
            self.message_input.clear()

    def display_message(self, message, is_self=False):
        if is_self:
            # Alinha mensagens enviadas à direita
            self.message_display.append(f"<p style='color:blue; text-align:right;'>{message}</p>")
        else:
            # Alinha mensagens recebidas à esquerda
            self.message_display.append(f"<p style='color:green; text-align:left;'>{message}</p>")

    def receive_messages(self):
        buffer = ''
        while True:
            try:
                data = self.client_socket.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self.process_message(message)
            except Exception as e:
                print(f"Erro ao receber mensagem: {e}")
                break

    def process_message(self, message):
        data = json.loads(message)
        
        # Processa a lista de clientes conectados
        if data["type"] == "client_list":
            self.update_client_list(data["clients"])
        
        # Processa mensagens diretas
        elif data["type"] == "message":
            sender_name = next((name for name, mac in self.nome_para_mac.items() if mac == data["sender"]), data["sender"])
            display_text = f"{sender_name}: {data['content']}"
            self.display_message(display_text)
            self.save_message(display_text)

    def update_client_list(self, clients):
        self.client_list_widget.clear()
        self.dest_selector.clear()
        
        for client in clients:
            if client["mac"] != self.mac_id:
                self.client_list_widget.addItem(client["name"])
                self.dest_selector.addItem(client["name"])
                self.nome_para_mac[client["name"]] = client["mac"]

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())
