import pickle
import pandas as pd
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(settings.BASE_DIR, 'model.pkl')
MODEL = None

try:
    with open(MODEL_PATH, 'rb') as f:
        MODEL = pickle.load(f)
    logger.info("Modelo de IA (model.pkl) carregado com sucesso.")
except Exception as e:
    logger.error(f"Erro ao carregar o modelo de IA: {e}", exc_info=True)

def predict_iqa_value(input_data: dict) -> float:
    """
    Usa o modelo de IA para prever o valor final do IQA.
    Retorna um único valor float.
    """
    if MODEL is None:
        logger.warning("Modelo não carregado. Retornando IQA padrão de 50.")
        return 50.0

    try:
        # Prepara os dados de entrada no formato exato que o modelo espera (DataFrame)
        X_new = pd.DataFrame([{
            'Coloração': input_data.get('coloracao', 15.5), 
            'Condutividade': input_data.get('condutividade'),
            'pH': input_data.get('ph'),
            'Temperatura da Água': input_data.get('temperatura'),
            'Turbidez': input_data.get('turbidez')
        }])

        # Faz a predição. O modelo retorna uma lista com um único valor.
        prediction = MODEL.predict(X_new)
        
        # Pega o primeiro e único valor da predição.
        predicted_iqa = float(prediction[0])
        
        logger.info(f"Valor de IQA predito pelo modelo: {predicted_iqa}")
        return predicted_iqa

    except Exception as e:
        logger.error(f"Erro durante a predição do IQA: {e}", exc_info=True)
        return 50.0 # Retorna um valor padrão em caso de erro