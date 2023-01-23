import serial
import time
import datetime
import struct
import math
from datetime import datetime

from threading import Event, Thread

from uart_modbus.uart import UART
from pid.pid import PID
from pwm_gpio.forno import Forno
from utils.log import escreverLog
from temp_ambiente.i2c import temperatura_ambiente


class Main:
    port = '/dev/serial0'
    baudrate = 9600
    matricula = [5, 1, 9, 5]
    timeout = 0.5

    def __init__(self):
        self.uart = UART(self.port, self.baudrate, self.timeout)
        self.ajuste_parametros()
        self.forno = Forno()
        self.inicia_variaveis()
        self.inicia_eventos()
        self.inicia_servicos()

    def ajuste_parametros(self):
        escolha = input(
            "Escolha:\n1 - Configurar parametros do Kp, Ki e KD\n2 - Definir configuração padrão (recomendado)\n")
        if(escolha == 1):
            kp = input("\nDigite o Kp: ")
            ki = input("\nDigite o Ki: ")
            kd = input("\nDigite o Kd: ")
            self.pid = PID(kp, ki, kd)
        elif(escolha == 2):
            self.pid = PID(30.0, 0.2, 400.0)
        else:
            self.pid = PID(30.0, 0.2, 400.0)

    def inicia_variaveis(self):
        self.menu = -1
        self.pid_value = 0
        self.temp_inter = 0
        self.temp_ref = 0
        self.temp_ambiente = 0
        self.tempo_seg = 0
        self.tempo_ref = 0

    def inicia_eventos(self):
        self.ligado = Event()
        self.funcionando = Event()
        self.aquecendo = Event()
        self.resfriando = Event()
        self.temporizador = Event()
        self.enviando = Event()

    def liga(self):
        self.enviando.set()
        comando_estado = b'\x01\x16\xd3'

        self.uart.envia(comando_estado, self.matricula, b'\x01', 8)
        dados = self.uart.recebe()

        if dados is not None:
            self.para()
            self.seta_tempo(0)
            self.ligado.set()

        self.enviando.clear()

    def desliga(self):
        self.enviando.set()
        comando_estado = b'\x01\x16\xd3'

        self.uart.envia(comando_estado, self.matricula, b'\x00', 8)
        dados = self.uart.recebe()

        if dados is not None:
            self.para()
            self.ligado.clear()

        self.enviando.clear()

    def inicia(self):
        self.enviando.set()
        comando_estado = b'\x01\x16\xd5'

        self.uart.envia(comando_estado, self.matricula, b'\x01', 8)
        dados = self.uart.recebe()

        if dados is not None:
            self.funcionando.set()

        self.enviando.clear()

    def para(self):
        self.enviando.set()
        comando_estado = b'\x01\x16\xd5'

        self.uart.envia(comando_estado, self.matricula, b'\x00', 8)
        dados = self.uart.recebe()

        if dados is not None:
            self.funcionando.clear()

        self.enviando.clear()

    def envia_sinal_controle(self, pid):
        self.enviando.set()
        comando_aquec = b'\x01\x16\xd1'
        valor = (round(pid)).to_bytes(4, 'little', signed=True)

        self.uart.envia(comando_aquec, self.matricula, valor, 11)
        self.uart.recebe()

        self.enviando.clear()

    def seta_forno(self):
        if self.ligado.is_set() and self.funcionando.is_set():
            self.pid_value = self.pid.pid_controle(
                self.temp_ref, self.temp_inter)
            self.envia_sinal_controle(self.pid_value)

            if(self.temp_inter < self.temp_ref):
                print("\n--------AQUECENDO--------\n")
                print('\nVALOR PID :::::::::::: ', self.pid_value)
                print("\nTEMP. INTERNA ::::::::", self.temp_inter)
                print("\nTEMP. REFERENCIA :::::", self.temp_ref)
                print("\nTEMP. AMBIENTE :::::::", self.temp_ambiente, "\n")

                self.forno.aquecer(int(abs(self.pid_value)))
                self.forno.resfriar(0)
                self.aquecendo.set()
                self.resfriando.clear()

            elif(self.temp_inter > self.temp_ref):
                print("\n--------RESFRIANDO--------\n")
                print('\nVALOR PID :::::::::::: ', self.pid_value)
                print("\nTEMP. INTERNA ::::::::", self.temp_inter)
                print("\nTEMP. REFERENCIA :::::", self.temp_ref)
                print("\nTEMP. AMBIENTE :::::::", self.temp_ambiente, "\n")
                if (self.pid_value < 0 and self.pid_value > -40):
                    self.forno.resfriar(40)
                else:
                    self.forno.resfriar(abs(int(self.pid_value)))

                self.forno.aquecer(0)
                self.aquecendo.clear()
                self.resfriando.set()

    def conta_tempo(self):
        while self.tempo_seg > 0:
            time.sleep(2)
            self.tempo_seg -= 1

    def seta_tempo(self, tempo):
        self.enviando.set()
        comando_estado = b'\x01\x16\xd6'
        valor = tempo.to_bytes(4, 'little')

        self.uart.envia(comando_estado, self.matricula, valor, 11)
        dados = self.uart.recebe()

        self.tempo_ref = tempo
        self.tempo_seg = tempo * 60

        self.enviando.clear()

    def trata_botao(self, bytes):
        botao = int.from_bytes(bytes, 'little') % 10
        print('botao:', botao)
        if botao == 1:
            self.liga()
        elif botao == 2:
            self.desliga()
        elif botao == 3:
            self.inicia()
        elif botao == 4:
            self.para()
        elif botao == 5:
            tempo = self.tempo_ref + 1
            self.seta_tempo(tempo + 1)
        elif botao == 6:
            tempo = self.tempo_ref - 1
            if tempo < 0:
                tempo = 0
            self.seta_tempo(tempo - 1)

    def trata_temp_int(self, bytes):
        temp = struct.unpack('f', bytes)[0]

        if temp > 0 and temp < 100:
            self.temp_inter = temp

        self.seta_forno()
        if self.temporizador.is_set():
            self.conta_tempo()

    def trata_temp_ref(self, bytes):
        temp = struct.unpack('f', bytes)[0]

        if temp > 0 and temp < 100:
            self.temp_ref = temp

    def solicita_botao(self):
        comando_botao = b'\x01\x23\xc3'

        self.uart.envia(comando_botao, self.matricula, b'', 7)
        dados = self.uart.recebe()

        if dados is not None:
            self.trata_botao(dados)

    def solicita_temp_int(self):
        comando_temp = b'\x01\x23\xc1'

        self.uart.envia(comando_temp, self.matricula, b'', 7)
        dados = self.uart.recebe()

        if dados is not None:
            self.trata_temp_int(dados)

    def solicita_temp_ref(self):
        comando_temp = b'\x01\x23\xc2'

        self.uart.envia(comando_temp, self.matricula, b'', 7)
        dados = self.uart.recebe()

        if dados is not None:
            self.trata_temp_ref(dados)

    def envia_temp_ambiente(self):
        self.enviando.set()

        self.temp_ambiente = temperatura_ambiente()
        comando_aquec = b'\x01\x16\xd6'

        valor = struct.pack('!f', self.temp_ambiente)
        valor = valor[::-1]

        self.uart.envia(comando_aquec, self.matricula, valor, 11)
        self.uart.recebe()

        self.enviando.clear()

    def rotina(self):
        while True:
            self.solicita_botao()
            self.solicita_temp_int()
            self.solicita_temp_ref()
            self.envia_temp_ambiente()
            time.sleep(1)

            mensagem = f'-------- {datetime.now()} -------- \nTemperatura interna: {round(self.temp_inter, 2)} \nTemperatura ambiente: {round(self.temp_ambiente, 2)} \nTemperatura de referência: {self.temp_ref}\nPID: {self.pid_value}% \n'
            escreverLog(mensagem)
            time.sleep(1)

    def inicia_servicos(self):
        self.liga()

        thread_rotina = Thread(target=self.rotina, args=())
        thread_rotina.start()

        print('Forno iniciado')


Main()
