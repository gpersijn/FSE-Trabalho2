def escreverLog(mensagem):
    log = open("src/log/log.csv", "a")
    log.write(f"{mensagem}\n")
    log.close()
