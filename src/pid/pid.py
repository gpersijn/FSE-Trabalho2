class PID:
    T = 1.0
    erro_total, erro_anterior, sinal_de_controle = 0.0, 0.0, 0.0
    sinal_de_controle_MAX, sinal_de_controle_MIN = 100.0, -100.0

    def __init__(self, Kp, Ki, Kd):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd

    def pid_controle(self, referencia, saida_medida):
        erro = referencia - saida_medida
        self.erro_total += erro  # Acumula o erro (Termo Integral)

        if self.erro_total >= self.sinal_de_controle_MAX:
            self.erro_total = self.sinal_de_controle_MAX
        elif self.erro_total <= self.sinal_de_controle_MIN:
            self.erro_total = self.sinal_de_controle_MIN

        # Diferença entre os erros (Termo Derivativo)
        delta_error = erro - self.erro_anterior
        self.sinal_de_controle = self.Kp * erro + (self.Ki * self.T) * self.erro_total + (
            self.Kd / self.T) * delta_error  # PID calcula sinal de controle

        if self.sinal_de_controle >= self.sinal_de_controle_MAX:
            self.sinal_de_controle = self.sinal_de_controle_MAX
        elif self.sinal_de_controle <= self.sinal_de_controle_MIN:
            self.sinal_de_controle = self.sinal_de_controle_MIN

        self.erro_anterior = erro

        return self.sinal_de_controle
