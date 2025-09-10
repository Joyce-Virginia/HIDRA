# iotmonitor/firebase_service.py
import firebase_admin
from firebase_admin import credentials, db
from django.conf import settings
from django.core.cache import cache
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import os
import threading
from firebase_admin import storage
import math
from firebase_admin import credentials, db, storage

from . import ml_predictor

logger = logging.getLogger(__name__)
firebase_logger = logging.getLogger('firebase')


class FirebaseService:
    """
    Serviço para gerenciar conexão e operações com Firebase Realtime Database
    """
    _instance: Optional['FirebaseService'] = None
    _lock = threading.Lock()

    def __new__(cls):
        # Agora esta verificação funcionará corretamente
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FirebaseService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.app = None
            self.db_ref = None
            self.initialized = False
            self._initialize_firebase()

    def _initialize_firebase(self):
        """
        Inicializa a conexão com o Firebase de forma robusta, funcionando
        tanto na Render (variável de ambiente) quanto localmente (ficheiro).
        """
        try:
            # Este serviço irá apenas reutilizar a conexão existente.
            if not firebase_admin._apps:
                # Esta mensagem de erro indica um problema de configuração mais sério
                # se a app não foi inicializada antes de o serviço ser chamado.
                raise RuntimeError("A aplicação Firebase não foi inicializada. Verifique a sua configuração em settings.py.")

            self.app = firebase_admin.get_app()
            self.db_ref = db.reference('/')
            self.initialized = True
            
            # A mensagem de log confirma que a conexão está a ser reutilizada com sucesso.
            firebase_logger.info("Serviço Firebase conectado à aplicação existente com sucesso.")

        except Exception as e:
            firebase_logger.error(f"Erro ao conectar-se à aplicação Firebase existente: {e}", exc_info=True)
            self.initialized = False

    def test_connection(self) -> bool:
        """ Testa a conexão com Firebase """
        try:
            if not self.initialized or not self.db_ref:
                return False
            # Usar uma chamada que não gera muito log para um simples teste
            self.db_ref.child('last_test').get(shallow=True)
            return True
        except Exception as e:
            firebase_logger.warning(f"Teste de conexão Firebase falhou: {e}")
            return False

    def get_latest_reading_from_leituras(self) -> Optional[Dict[str, Any]]:
        """
        Obtém a leitura mais recente do nó /leituras de forma segura.
        """
        

        if not self.initialized:
            firebase_logger.warning(
                "Firebase não inicializado, impossível buscar leituras.")
            return None

        try:
            cache_key = 'firebase_latest_leitura'
            cached_data = cache.get(cache_key)
            if cached_data:
                firebase_logger.debug("Última leitura obtida do cache.")
                return cached_data

            leituras_ref = self.db_ref.child('values')
            latest_reading_node = leituras_ref.order_by_key().limit_to_last(1).get()

            if not latest_reading_node or not isinstance(latest_reading_node, dict):
                firebase_logger.warning(
                    f"Nó de leitura inválido ou não encontrado em /values: {latest_reading_node}")
                return None

            raw_data = None
            try:
                id_leitura = list(latest_reading_node.keys())[0]
                raw_data = latest_reading_node[id_leitura]

                if not isinstance(raw_data, dict):
                    firebase_logger.error(
                        f"Payload para a leitura {id_leitura} não é um dicionário. Recebido: {type(raw_data)}")
                    return None

            except (IndexError, AttributeError):
                firebase_logger.error(
                    "Erro ao extrair dados da estrutura do Firebase em /values.", exc_info=True)
                return None

            if not raw_data:
                firebase_logger.error(
                    "Falha ao extrair raw_data da estrutura do Firebase.")
                return None

            formatted_data = self._format_leitura_data(raw_data)

            cache.set(cache_key, formatted_data, 30)
            firebase_logger.info(
                "Dados da última leitura (de /values) obtidos e formatados com sucesso.")
            return formatted_data

        except Exception as e:
            firebase_logger.error(
                f"Erro ao obter a última leitura do Firebase: {e}", exc_info=True)
            return None

    def _convert_raw_temp_to_celsius(self, raw_adc: float) -> float:
        """
        Converte o valor cru do ADC do sensor de temperatura para graus Celsius.
        """
        # Adiciona uma verificação para valores fora da faixa esperada (0-4095)
        if not (0 < raw_adc < 4095):
            logger.warning(
                f"Valor de ADC da temperatura ('{raw_adc}') está fora da faixa válida. Retornando 25.0°C.")
            return 25.0

        try:
            B = 3950
            R0 = 10000
            T0 = 298.15

            VOUT = raw_adc * (3.3 / 4095.0)
            R = (10000 * VOUT) / (3.3 - VOUT)

            inv_T = (1.0 / T0) + (1.0 / B) * math.log(R / R0)
            temp_kelvin = 1.0 / inv_T
            temp_celsius = temp_kelvin - 273.15

            return round(temp_celsius, 2)
        except (ValueError, ZeroDivisionError) as e:
            logger.warning(
                f"Não foi possível converter a temperatura crua '{raw_adc}': {e}. Retornando 25.0°C.")
            return 25.0  # Retorna um valor padrão seguro

    def _format_leitura_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata dados, converte temperatura e usa valores padrão para campos ausentes.
        """
        try:
            # 1. Converte a temperatura
            raw_temp = float(raw_data.get('temperatura', 4095))
            temp_celsius = self._convert_raw_temp_to_celsius(raw_temp)

            # 2. Pega os valores conhecidos do Firebase
            known_values = {
                'Temperatura': temp_celsius,
                'pH': float(raw_data.get('ph', 7.0)),
                'Turbidez': float(raw_data.get('turbidez', 0.0)),
            }

            # 3. Pega e formata o timestamp
            timestamp_str = raw_data.get('timestamp', '')
            iso_timestamp = datetime.now().isoformat()
            try:
                dt_obj = datetime.strptime(timestamp_str, '%d-%m-%Y-%H-%M-%S')
                iso_timestamp = dt_obj.isoformat()
            except (ValueError, TypeError):
                pass

            # 4. Junta os valores conhecidos com os valores padrão para os ausentes
            final_data = {
                'Temperatura': known_values['Temperatura'],
                'pH': known_values['pH'],
                'Turbidez': known_values['Turbidez'],

                # Usando valores padrão seguros para os campos ausentes
                'OD': 7.5,
                'DBO': 5.0,
                'Coliformes': 200.0,
                'NT': 10.0,
                'FT': 1.0,
                'Residuos': float(raw_data.get('solidos', 0)),
                'timestamp': iso_timestamp
            }
            return final_data

        except Exception as e:
            logger.error(f"Erro Crítico ao formatar dados: {e}", exc_info=True)
            # Retorna um dicionário de fallback seguro
            return {'Temperatura': 25, 'pH': 7, 'Turbidez': 0, 'OD': 7.8, 'DBO': 5, 'Coliformes': 200, 'NT': 10, 'FT': 1, 'Residuos': 0, 'timestamp': datetime.now().isoformat()}

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        Determina o status do dispositivo verificando a idade da última leitura.
        """
        try:
            # Reutiliza a função que já busca e formata a última leitura
            latest_reading = self.get_latest_reading_from_leituras()

            if latest_reading and 'timestamp' in latest_reading:
                timestamp_str = latest_reading['timestamp']
                last_seen_dt = datetime.fromisoformat(timestamp_str)

                # Considera offline se a última leitura tem mais de 5 minutos
                if (datetime.now() - last_seen_dt).total_seconds() > 300:
                    status = "offline"
                    firebase_logger.warning(
                        f"Dispositivo {device_id} considerado offline (última leitura > 5 min atrás).")
                else:
                    status = "online"

                return {
                    'status': status,
                    'last_seen': last_seen_dt.strftime('%d/%m/%Y %H:%M:%S')
                }
        except Exception as e:
            firebase_logger.error(
                f"Erro ao obter status do dispositivo {device_id}: {e}")

        # Retorno padrão em caso de erro ou nenhum dado
        return {
            'status': 'desconhecido',
            'last_seen': 'Nunca'
        }
    # --- NOVO MÉTODO PARA BUSCAR O HISTÓRICO ---

    def get_all_leituras(self) -> list[Dict[str, Any]]:
        """
        Obtém TODAS as leituras do nó /leituras e as retorna como uma lista.
        """
        if not self.initialized:
            firebase_logger.warning(
                "Firebase não inicializado, impossível buscar histórico.")
            return []

        try:
            # Tenta buscar do cache primeiro para aliviar o Firebase
            cache_key = 'firebase_all_leituras'
            cached_data = cache.get(cache_key)
            if cached_data:
                firebase_logger.debug("Histórico de leituras obtido do cache.")
                return cached_data

            leituras_ref = self.db_ref.child('values')
            all_readings_raw = leituras_ref.order_by_key().get()

            if not all_readings_raw or not isinstance(all_readings_raw, dict):
                firebase_logger.warning(
                    "Nenhum dado histórico encontrado em /leituras.")
                return []

            # Processa cada leitura e a adiciona a uma lista
            formatted_list = []
            for id_leitura, raw_data in all_readings_raw.items():
                if isinstance(raw_data, dict):
                    try:
                        formatted_data = self._format_leitura_data(raw_data)
                        formatted_list.append(formatted_data)
                    except Exception as e:
                        firebase_logger.warning(
                            f"Erro ao formatar leitura histórica #{id_leitura}: {e}")

            # Salva a lista no cache por 60 segundos
            cache.set(cache_key, formatted_list, 60)

            firebase_logger.info(
                f"{len(formatted_list)} leituras históricas processadas com sucesso.")
            return formatted_list

        except Exception as e:
            firebase_logger.error(
                f"Erro crítico ao obter histórico de leituras: {e}", exc_info=True)
            return []

    def upload_image_to_storage(self, file_path: str, destination_blob_name: str) -> Optional[str]:
        """
        Faz upload de um arquivo para o Firebase Storage e retorna sua URL pública.

        :param file_path: Caminho local do arquivo a ser enviado.
        :param destination_blob_name: Nome do arquivo no Storage (ex: 'imagens/sensores/sensor1.jpg').
        :return: A URL pública do arquivo ou None em caso de erro.
        """
        if not self.initialized:
            firebase_logger.error(
                "Firebase não inicializado. Upload de imagem cancelado.")
            return None

        try:
            # Obtenha o bucket a partir da sua URL de database
            # Ex: 'gs://hidra-eco-default-rtdb.appspot.com'
            bucket_name = self.app.options['storageBucket']
            bucket = storage.bucket(bucket_name)

            # Cria o "blob" (o objeto/arquivo no Storage)
            blob = bucket.blob(destination_blob_name)

            # Faz o upload do arquivo
            blob.upload_from_filename(file_path)

            # Torna o arquivo publicamente acessível para ser usado em tags <img>
            blob.make_public()

            firebase_logger.info(
                f"Imagem '{file_path}' enviada para '{destination_blob_name}' com sucesso.")

            # Retorna a URL pública
            return blob.public_url

        except Exception as e:
            firebase_logger.error(
                f"Erro ao fazer upload da imagem: {e}", exc_info=True)
            return None

    def save_leitura_to_rtdb(self, sensor_data: Dict[str, Any]) -> (bool, Optional[str]):
        """
        Salva um dicionário de dados de leitura em um novo nó em /leituras.
        Usa push() para gerar um ID único e cronológico.
        Retorna (sucesso, id_da_nova_leitura).
        """
        if not self.initialized:
            firebase_logger.error(
                "Firebase não inicializado. Não foi possível salvar a leitura.")
            return False, None

        try:
            leituras_ref = self.db_ref.child('leituras')
            # O método push() cria um novo registro com um ID único e ordenado por tempo
            new_leitura_ref = leituras_ref.push(sensor_data)

            firebase_logger.info(
                f"Nova leitura salva no RTDB com ID: {new_leitura_ref.key}")
            return True, new_leitura_ref.key
        except Exception as e:
            firebase_logger.error(
                f"Erro ao salvar leitura no RTDB: {e}", exc_info=True)
            return False, None

    def get_latest_image_url(self) -> Optional[str]:
        """
        Busca no Firebase Storage pela imagem mais recente na RAIZ do bucket
        e retorna sua URL pública (SEM CACHE).
        """
        logger.info(
            "--- Iniciando busca pela imagem mais recente no Storage (na raiz) ---")

        if not self.initialized:
            logger.warning(
                "Firebase não inicializado, impossível buscar imagem.")
            return None

        try:
            bucket_name = self.app.options.get('storageBucket')
            if not bucket_name:
                logger.error(
                    "Bucket ID do Storage não encontrado na configuração do Firebase.")
                return None

            bucket = storage.bucket(bucket_name)

            logger.info(
                f"Buscando arquivos na raiz do bucket '{bucket_name}'...")
            blobs = list(bucket.list_blobs())

            if not blobs:
                logger.info("Nenhuma imagem encontrada no Firebase Storage.")
                return None

            latest_blob = max(blobs, key=lambda b: b.name)

            logger.info(
                f"Arquivo determinado como o mais recente: '{latest_blob.name}'")

            latest_blob.make_public()
            public_url = latest_blob.public_url

            logger.info(f"URL pública gerada: {public_url}")

            return public_url

        except Exception as e:
            logger.error(
                f"Erro ao buscar imagem mais recente do Storage: {e}", exc_info=True)
            return None


# Instância global do serviço (deve vir DEPOIS da definição da classe)
firebase_service = FirebaseService()

# --- FUNÇÃO AUXILIAR ATUALIZADA ---
# A views.py chama esta função. Agora, ela usará a nova lógica.
# --- FUNÇÃO AUXILIAR GLOBAL ---


def get_firebase_sensor_data() -> Optional[Dict[str, float]]:
    """
    Função auxiliar para obter dados dos sensores do Firebase.
    """
    try:
        data = firebase_service.get_latest_reading_from_leituras()

        if data:
            return data
        else:
            firebase_logger.warning(
                "Fallback: Nenhum dado retornado do Firebase. Usando dados de exemplo.")
            return {
                'Coliformes': 30.96, 'pH': 8.9, 'DBO': 6.06, 'NT': 2.10, 'FT': 0.22,
                'Temperatura': 25.0, 'Turbidez': 32.62, 'Residuos': 255.75, 'OD': 7.28
            }
    except Exception as e:
        logger.error(
            f"Erro crítico ao chamar get_latest_reading_from_leituras: {e}", exc_info=True)
        return {
            'Coliformes': 0, 'pH': 7.0, 'DBO': 0, 'NT': 0, 'FT': 0,
            'Temperatura': 25, 'Turbidez': 0, 'Residuos': 0, 'OD': 0
        }

# --- NOVA FUNÇÃO AUXILIAR GLOBAL ---


def get_all_firebase_leituras() -> list[Dict[str, Any]]:
    """
    Função auxiliar global para obter todo o histórico de leituras.
    """
    try:
        return firebase_service.get_all_leituras()
    except Exception as e:
        logger.error(f"Erro ao chamar get_all_leituras: {e}", exc_info=True)
        return []


# Instância global do serviço
firebase_service = FirebaseService()

# A função save_firebase_sensor_data não é usada pelo ESP32, mas pode ser mantida
# para salvar dados a partir do Django, se necessário.


def save_firebase_sensor_data(sensor_data: Dict[str, Any], device_id: str = "ESP32_001") -> bool:
    """
    Função auxiliar para salvar dados dos sensores no Firebase (na estrutura antiga /sensors/).
    """
    try:
        # Note que esta função salva no caminho antigo /sensors/
        return firebase_service.save_sensor_data(sensor_data, device_id)
    except Exception as e:
        logger.error(f"Erro ao salvar dados no Firebase: {e}")
        return False
