import sys
import os
import random
import socket
import threading
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QListWidget, QTextEdit, QTabWidget, QInputDialog
from PyQt5.QtCore import Qt

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat - Cliente")
        self.setGeometry(100, 100, 600, 500)
        
        self.mac_id = self.load_or_generate_mac()
        self.user_name = self.load_or_request_name()
        self.message_history_dir = "chat_histories"
        os.makedirs(self.message_history_dir, exist_ok=True)
        self.nome_para_mac = {}
        self.active_chat = None
        self.unread_messages = {}
        self.pending_messages = {}  # Dicionário para armazenar mensagens não lidas

        # Conectar ao servidor
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('127.0.0.1', 12345))
        self.client_socket.sendall((json.dumps({"type": "register", "mac": self.mac_id, "name": self.user_name}) + '\n').encode())
        
        # Criar a interface
        self.initUI()

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
        self.client_list_widget.itemClicked.connect(self.change_chat)
        left_layout.addWidget(client_label)
        left_layout.addWidget(self.client_list_widget)
        main_layout.addLayout(left_layout, 1)

        # Área de mensagens e entrada
        right_layout = QVBoxLayout()

        # Área de exibição das abas de conversa
        self.chat_tabs = QTabWidget()
        self.chat_tabs.currentChanged.connect(self.switch_tab)
        right_layout.addWidget(self.chat_tabs, 4)

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

    def load_message_history(self, contact_name):
        file_path = os.path.join(self.message_history_dir, f"{contact_name}_history.txt")
        messages = []
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                messages = file.readlines()
        return messages

    def save_message(self, contact_name, message):
        file_path = os.path.join(self.message_history_dir, f"{contact_name}_history.txt")
        with open(file_path, "a") as file:
            file.write(message + "\n")

    def send_message(self):
        message = self.message_input.text()
        if message and self.active_chat:
            dest_mac = self.nome_para_mac.get(self.active_chat, "")
            if dest_mac:
                display_text = f"Você: {message}"
                self.display_message(self.active_chat, display_text, True)
                self.save_message(self.active_chat, display_text)

                # Formata e envia a mensagem como JSON para o servidor
                data = json.dumps({"type": "message", "dest": dest_mac, "content": message}) + '\n'
                self.client_socket.sendall(data.encode())
                self.message_input.clear()

    def display_message(self, contact_name, message, is_self=False):
        # Encontra ou cria a aba de chat para o contato
        tab = self.get_chat_tab(contact_name)
        if is_self:
            # Alinha mensagens enviadas à direita
            tab.append(f"<p style='color:blue; text-align:right;'>{message}</p>")
        else:
            # Alinha mensagens recebidas à esquerda
            tab.append(f"<p style='color:green; text-align:left;'>{message}</p>")

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
        
        if data["type"] == "client_list":
            self.update_client_list(data["clients"])
        
        elif data["type"] == "message":
            sender_mac = data["sender"]
            sender_name = next((name for name, mac in self.nome_para_mac.items() if mac == sender_mac), sender_mac)
            display_text = f"{sender_name}: {data['content']}"
            self.save_message(sender_name, display_text)

            if sender_name != self.active_chat:
                # Armazena a mensagem como não lida se a aba não estiver ativa
                if sender_name not in self.pending_messages:
                    self.pending_messages[sender_name] = []
                self.pending_messages[sender_name].append(display_text)
                self.unread_messages[sender_name] = True
                self.update_client_list_display()
            else:
                self.display_message(sender_name, display_text)

    def update_client_list(self, clients):
        self.nome_para_mac = {client["name"]: client["mac"] for client in clients if client["mac"] != self.mac_id}
        self.update_client_list_display()

    def update_client_list_display(self):
        self.client_list_widget.clear()
        for name in self.nome_para_mac:
            item_text = f"{name} (Novo)" if self.unread_messages.get(name) else name
            self.client_list_widget.addItem(item_text)

    def get_chat_tab(self, contact_name):
        index = self.chat_tabs.indexOf(self.chat_tabs.findChild(QTextEdit, contact_name))
        if index != -1:
            return self.chat_tabs.widget(index)

        # Criar nova aba se não existir
        tab = QTextEdit()
        tab.setReadOnly(True)
        tab.setObjectName(contact_name)
        self.chat_tabs.addTab(tab, contact_name)

        # Carregar histórico na nova aba
        messages = self.load_message_history(contact_name)
        for message in messages:
            self.display_message(contact_name, message.strip(), "Você:" in message)
        return tab

    def change_chat(self, item):
        contact_name = item.text().replace(" (Novo)", "")
        self.unread_messages[contact_name] = False
        self.active_chat = contact_name
        self.update_client_list_display()
        self.chat_tabs.setCurrentWidget(self.get_chat_tab(contact_name))
        
        # Exibir mensagens pendentes (não lidas) na aba ativa
        if contact_name in self.pending_messages:
            for msg in self.pending_messages[contact_name]:
                self.display_message(contact_name, msg)
            del self.pending_messages[contact_name]  # Limpar as mensagens pendentes

    def switch_tab(self, index):
        widget = self.chat_tabs.widget(index)
        if widget:
            self.active_chat = widget.objectName()
            self.update_client_list_display()
            
            # Exibir mensagens pendentes ao mudar para a aba
            if self.active_chat in self.pending_messages:
                for msg in self.pending_messages[self.active_chat]:
                    self.display_message(self.active_chat, msg)
                del self.pending_messages[self.active_chat]  # Limpar as mensagens pendentes

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())
