import math
import numpy as np

# Pesos dos parâmetros segundo CETESB
pesos = {
    'OD': 0.17,
    'DBO': 0.10,
    'Coliformes': 0.15,
    'pH': 0.12,
    'NT': 0.10,
    'FT': 0.10,
    'Temperatura': 0.10,
    'Turbidez': 0.08,
    'Residuos': 0.08
}

# Funções das curvas aproximadas (q_i)
def curva_Coliformes(coliformes):  # 1
    A1 = 98.03
    B1 = -36.45
    C1 = 3.138
    D1 = 0.06776
    log_cf = math.log10(coliformes)
    return A1 + (B1 * log_cf) + (C1 * (log_cf**2)) + (D1*(log_cf**3))


def curva_pH(ph):  # 2
    A2 = 0.05421
    B2 = 1.23
    C2 = -0.09873
    return A2 * ph ** ((B2*ph)+(C2*(ph**2)))+5.213


def curva_DBO(dbo):  # 3
    A3 = 102.6
    B3 = -0.1101
    return A3 * np.exp(B3 * dbo)


def curva_NT(nt):  # 4
    A4 = 98.96
    B4 = -0.2232
    C4 = -0.006457
    return A4 * (nt ** (B4 + C4 * nt))


def curva_FT(ft):  # 5
    A5 = 213.7
    B5 = -1.680
    C5 = 0.3325
    return A5 * math.exp(B5 * (ft ** C5))


def curva_Temperatura(delta_temp):  # 6
    A6 = 0.0003869
    B6 = 0.1815
    C6 = 0.01081
    return 1 / (A6 * ((delta_temp + B6) ** 2) + C6)


def curva_Turbidez(turb):  # 7
    A7 = 97.34
    B7 = -0.01139
    C7 = -0.04917
    return A7 * math.exp(B7 * turb + C7 * math.sqrt(turb))


def curva_Residuos(rt):  # 8
    A8 = 80.26
    B8 = -0.00107
    C8 = 0.03009
    D8 = -0.1185
    return A8 * math.exp(B8 * rt + C8 * math.sqrt(rt)) + D8 * rt


def curva_OD(od):  # 9
    A9 = 100.8
    B9 = -106
    C9 = -3745
    return A9 * math.exp(((od + B9) ** 2) / C9)


# Função para calcular o IQA
def calcular_IQA(valores):
    subindices = {
        'Coliformes': curva_Coliformes(valores['Coliformes']),
        'pH': curva_pH(valores['pH']),
        'DBO': curva_DBO(valores['DBO']),
        'NT': curva_NT(valores['NT']),
        'FT': curva_FT(valores['FT']),
        'Temperatura': curva_Temperatura(valores['Temperatura']),
        'Turbidez': curva_Turbidez(valores['Turbidez']),
        'Residuos': curva_Residuos(valores['Residuos']),
        'OD': curva_OD(valores['OD'])
    }

    iqa = 1
    for param, qi in subindices.items():
        iqa *= qi ** pesos[param]

    return round(iqa, 2), subindices


def classificar_IQA(iqa):
    if iqa > 79:
        return "Ótima"
    elif iqa > 51:
        return "Boa"
    elif iqa > 36:
        return "Regular"
    elif iqa > 19:
        return "Ruim"
    else:
        return "Péssima"


# Exemplo de uso: 
valores_exemplo = {
    'Coliformes': 33.96,     # NMP/100mL
    'pH': 8.41,             # UNT
    'DBO': 6.06,            # mg/L
    'NT': 2.10,             # mg/L
    'FT': 0.22,            # mg/L
    'Temperatura': 2,    # ∆T (diferença da temperatura da água e a ambiente)
    'Turbidez': 22.62,       # UNT
    'Residuos': 255.75,      # mg/L
    'OD': 7.28             # mg/L
}

iqa, subs = calcular_IQA(valores_exemplo)

print("Parâmetro       Valor Exemplo      Subíndice Calculado")
print("--------------------------------------------------------")
for k in valores_exemplo:
    valor = valores_exemplo[k]
    subindice = subs[k]
    print(f"{k:<15} {valor:<18} {subindice:.2f}")

classificacao = classificar_IQA(iqa)

print("--------------------------\------------------------------")
print(f"IQA Final: {iqa} → Classificação: {classificacao}")
