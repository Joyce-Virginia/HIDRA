# views.py

from django.shortcuts import render, redirect

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

from django.utils import timezone

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout

from django.contrib.auth.models import User

from django.contrib import messages

from django.http import JsonResponse

from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth.decorators import login_required

from django.core.validators import validate_email

from django.core.exceptions import ValidationError

from django.core.cache import cache

import json

import logging

from django.contrib.auth.decorators import login_required

from django.views.decorators.http import require_http_methods

from django.views.decorators.csrf import csrf_exempt, csrf_protect

from .utils import send_password_reset_email, validate_password_reset_token

from django.conf import settings

from .iqa_calculator import IQACalculator

# Importar serviço Firebase

from . import ml_predictor

from .firebase_service import firebase_service, get_firebase_sensor_data, save_firebase_sensor_data, get_all_firebase_leituras

from datetime import datetime


# Configurar logging
logger = logging.getLogger(__name__)


# Logger específico para dados dos sensores
sensor_logger = logging.getLogger('sensors')

# Logger para alertas
alert_logger = logging.getLogger('alerts')

# Logger para IQA
iqa_logger = logging.getLogger('iqa')

# Logger para conexões ESP
esp_logger = logging.getLogger('esp_connection')


def homepage(request):
    return render(request, 'iotmonitor/homepage.html')


def login(request):
    """
    View para autenticação de usuários
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        # Validações básicas
        if not email or not password:
            messages.error(request, 'Email e senha são obrigatórios.')
            return render(request, 'iotmonitor/login.html')

        try:
            # Validar formato do email
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Digite um email válido.')
            return render(request, 'iotmonitor/login.html')

        try:
            # Buscar usuário pelo email
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, 'Email ou senha incorretos.')
            logger.warning(
                f'Tentativa de login com email inexistente: {email}')
            return render(request, 'iotmonitor/login.html')

        # Autenticar usuário
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                auth_login(request, user)

                # Configurar sessão baseado no "lembrar-me"
                if not remember_me:
                    # Sessão expira quando o navegador fechar
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)  # 2 semanas

                logger.info(
                    f'Login bem-sucedido para usuário: {user.username}')
                messages.success(request, f'Bem-vindo, {user.username}!')

                # Redirecionar para próxima página se especificada
                next_page = request.GET.get('next', 'dashboard')
                return redirect(next_page)
            else:
                messages.error(request, 'Sua conta está desativada.')
        else:
            messages.error(request, 'Email ou senha incorretos.')
            logger.warning(
                f'Tentativa de login com credenciais inválidas para: {email}')

    return render(request, 'iotmonitor/login.html')


def cadastro(request):
    """
    View para cadastro de novos usuários
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        # Validações
        errors = []

        if not username or not email or not password or not password_confirm:
            errors.append('Todos os campos são obrigatórios.')

        if len(username) < 3:
            errors.append('Nome de usuário deve ter pelo menos 3 caracteres.')

        if not username.replace('_', '').isalnum():
            errors.append(
                'Nome de usuário pode conter apenas letras, números e underscore.')

        try:
            validate_email(email)
        except ValidationError:
            errors.append('Digite um email válido.')

        if len(password) < 8:
            errors.append('A senha deve ter pelo menos 8 caracteres.')

        if password != password_confirm:
            errors.append('As senhas não coincidem.')

        # Verificar se usuário já existe
        if User.objects.filter(username=username).exists():
            errors.append('Nome de usuário já existe.')

        if User.objects.filter(email=email).exists():
            errors.append('Email já está cadastrado.')

        # Se há erros, exibir e retornar
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'iotmonitor/cadastro.html')

        # Criar usuário
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name='',  # Pode ser adicionado depois no perfil
                last_name=''
            )

            logger.info(f'Novo usuário cadastrado: {username} ({email})')
            messages.success(
                request, 'Conta criada com sucesso! Faça login para continuar.')
            return redirect('login')

        except Exception as e:
            logger.error(f'Erro ao criar usuário {username}: {str(e)}')
            messages.error(
                request, 'Erro interno. Tente novamente em alguns minutos.')

    return render(request, 'iotmonitor/cadastro.html')


@require_http_methods(["GET", "POST"])
@csrf_protect
def logout_view(request):
    """
    View para logout de usuários
    Aceita tanto GET quanto POST para compatibilidade
    """
    if request.user.is_authenticated:
        username = request.user.username
        auth_logout(request)
        logger.info(f'Logout realizado para usuário: {username}')
        messages.success(request, 'Você foi desconectado com sucesso.')

    return redirect('homepage')

# Views AJAX para validações em tempo real


@csrf_exempt
def check_username(request):
    """
    View AJAX para verificar se username já existe
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()

            if not username:
                return JsonResponse({'exists': False, 'valid': False})

            exists = User.objects.filter(username=username).exists()
            valid = len(username) >= 3 and username.replace('_', '').isalnum()

            return JsonResponse({
                'exists': exists,
                'valid': valid,
                'message': 'Nome de usuário já existe.' if exists else ''
            })
        except Exception as e:
            logger.error(f'Erro na verificação de username: {str(e)}')
            return JsonResponse({'error': 'Erro interno'}, status=500)

    return JsonResponse({'error': 'Método não permitido'}, status=405)


@csrf_exempt
def check_email(request):
    """
    View AJAX para verificar se email já existe
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()

            if not email:
                return JsonResponse({'exists': False, 'valid': False})

            # Validar formato do email
            try:
                validate_email(email)
                valid = True
            except ValidationError:
                valid = False

            exists = User.objects.filter(
                email=email).exists() if valid else False

            return JsonResponse({
                'exists': exists,
                'valid': valid,
                'message': 'Email já está cadastrado.' if exists else 'Email inválido.' if not valid else ''
            })
        except Exception as e:
            logger.error(f'Erro na verificação de email: {str(e)}')
            return JsonResponse({'error': 'Erro interno'}, status=500)

    return JsonResponse({'error': 'Método não permitido'}, status=405)


def password_reset_request(request):
    """
    View para solicitar recuperação de senha
    """
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if not email:
            messages.error(request, 'Digite seu email.')
            return render(request, 'iotmonitor/registration/password_reset.html')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Digite um email válido.')
            return render(request, 'iotmonitor/registration/password_reset.html')

        try:
            user = User.objects.get(email=email)

            if send_password_reset_email(request, user):
                messages.success(request,
                                 'Se este email estiver cadastrado, você receberá instruções para redefinir sua senha.')
            else:
                messages.error(
                    request, 'Erro ao enviar email. Tente novamente.')

        except User.DoesNotExist:
            # Por segurança, não revelamos se o email existe ou não
            messages.success(request,
                             'Se este email estiver cadastrado, você receberá instruções para redefinir sua senha.')

        return redirect('password_reset_done')

    return render(request, 'iotmonitor/registration/password_reset.html')


def password_reset_confirm(request, uidb64, token):
    """
    View para confirmar e redefinir senha
    """
    user = validate_password_reset_token(uidb64, token)

    if user is None:
        messages.error(request, 'Link inválido ou expirado.')
        return redirect('password_reset')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not password or not password_confirm:
            messages.error(request, 'Todos os campos são obrigatórios.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})

        if len(password) < 8:
            messages.error(
                request, 'A senha deve ter pelo menos 8 caracteres.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})

        if password != password_confirm:
            messages.error(request, 'As senhas não coincidem.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})

        # Redefinir senha
        user.set_password(password)
        user.save()

        logger.info(f'Senha redefinida para usuário: {user.username}')
        messages.success(
            request, 'Senha redefinida com sucesso! Faça login com sua nova senha.')
        return redirect('login')

    return render(request, 'registration/password_reset_confirm.html', {'user': user})


def password_reset_done(request):
    """
    View de confirmação após solicitar recuperação
    """
    return render(request, 'registration/password_reset_done.html')


def password_reset_complete(request):
    """
    View de confirmação após redefinir senha
    """
    return render(request, 'registration/password_reset_complete.html')

# ==================== DASHBOARD COM IQA ====================


def get_sensor_data():
    """
    Obtém dados dos sensores, priorizando o Firebase com a nova estrutura do ESP32.
    """
    logger.debug(
        "Iniciando obtenção de dados dos sensores (nova estrutura ESP32)")

    try:
        # 1. Tentar obter a última leitura do Firebase a partir do caminho /leituras
        # Esta lógica deve idealmente estar em firebase_service.py
        # Aqui, simulamos a leitura e a transformação necessárias.

        # Supondo que get_firebase_sensor_data foi adaptado para buscar a última leitura em '/leituras'
        # e retorna um dicionário. Se não, a lógica seria:
        # firebase_leituras = firebase_service.get_data('/leituras', order_by_key=True, limit_to_last=1)
        # if firebase_leituras:
        #    # A resposta é um dicionário onde a chave é o ID da leitura
        #    leitura_key = list(firebase_leituras.keys())[0]
        #    # Dentro dele, outra chave é o timestamp
        #    timestamp_key = list(firebase_leituras[leitura_key].keys())[0]
        #    firebase_raw_data = firebase_leituras[leitura_key][timestamp_key]
        # else:
        #    firebase_raw_data = None

        # Para simplificar, vamos assumir que get_firebase_sensor_data retorna o último dado bruto
        firebase_raw_data = get_firebase_sensor_data(
            "leituras")  # "leituras" é o novo alvo

        if firebase_raw_data:
            logger.info("Dados brutos obtidos do Firebase (caminho /leituras)")

            # 2. MAPEAR E TRANSFORMAR OS DADOS DO FIREBASE PARA O FORMATO DO DJANGO
            # O ESP32 envia 'oxigenio', 'solidos', etc. O Django espera 'OD', 'Residuos'.
            sensor_data = {
                'Temperatura': float(firebase_raw_data.get('temperatura', 25)),
                'pH': float(firebase_raw_data.get('ph', 7)),
                # Mapeamento: oxigenio -> OD
                'OD': float(firebase_raw_data.get('oxigenio', 0)),
                'DBO': float(firebase_raw_data.get('dbo', 0)),
                'Coliformes': float(firebase_raw_data.get('coliformes', 0)),
                # Mapeamento: nitrogenio -> NT (Nitrogênio Total)
                'NT': float(firebase_raw_data.get('nitrogenio', 0)),
                # Mapeamento: fosforo -> FT (Fósforo Total)
                'FT': float(firebase_raw_data.get('fosforo', 0)),
                'Turbidez': float(firebase_raw_data.get('turbidez', 0)),
                # Mapeamento: solidos -> Residuos
                'Residuos': float(firebase_raw_data.get('solidos', 0)),
            }

            # 3. CONVERTER O TIMESTAMP
            # O ESP32 envia "DD-MM-YYYY-HH-MM-SS"
            timestamp_str = firebase_raw_data.get('timestamp')
            try:
                # Converte o formato customizado para um objeto datetime
                data_time = datetime.strptime(
                    timestamp_str, '%d-%m-%Y-%H-%M-%S')
                # Converte para o formato ISO que o resto do código usa
                sensor_data['timestamp'] = data_time.isoformat()
            except (ValueError, TypeError):
                logger.warning(
                    f"Timestamp em formato inesperado: {timestamp_str}. Usando o horário atual.")
                sensor_data['timestamp'] = datetime.now().isoformat()

            # Verificar se os dados são recentes
            data_time_obj = datetime.fromisoformat(sensor_data['timestamp'])
            time_diff = datetime.now() - data_time_obj.replace(tzinfo=None)

            if time_diff.total_seconds() < 300:  # 5 minutos
                logger.info(
                    "Dados recentes do Firebase processados e mapeados com sucesso.")
                # Salva no cache com os nomes corretos
                cache.set('sensor_data', sensor_data, 300)
                return sensor_data
            else:
                logger.warning(
                    f"Dados do Firebase são antigos: {time_diff.total_seconds():.0f} segundos.")

    except Exception as e:
        logger.error(
            f"Erro crítico ao obter ou processar dados do Firebase: {e}")

    # Fallback para o cache ou dados de emergência se o Firebase falhar ou os dados forem antigos
    cached_data = cache.get('sensor_data')
    if cached_data:
        logger.info("Usando dados do cache local como fallback.")
        return cached_data

    logger.warning("Usando dados de fallback de emergência.")
    return {
        'Coliformes': 0, 'pH': 7.0, 'DBO': 0, 'NT': 0, 'FT': 0,
        'Temperatura': 25, 'Turbidez': 0, 'Residuos': 0, 'OD': 0,
        'timestamp': datetime.now().isoformat()
    }


@csrf_exempt
@require_http_methods(["POST"])
def esp_sensor_data(request):
    """
    Endpoint para receber dados dos sensores com integração Firebase
    """
    client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
    esp_logger.info(f"Conexão recebida de IP: {client_ip}")

    try:
        # Parse do JSON
        raw_data = request.body.decode('utf-8')
        esp_logger.debug(f"Dados brutos recebidos: {raw_data}")

        data = json.loads(raw_data)
        device_id = data.get('device_id', 'ESP32_001')

        esp_logger.info(f"Processando dados do dispositivo: {device_id}")

        # Validação de campos obrigatórios
        required_fields = ['coliformes', 'ph', 'dbo', 'nt', 'ft',
                           'temperatura', 'turbidez', 'residuos', 'od']

        missing_fields = [
            field for field in required_fields if field not in data]
        if missing_fields:
            error_msg = f'Campos obrigatórios ausentes: {missing_fields}'
            esp_logger.warning(f"Dispositivo {device_id}: {error_msg}")
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        # Conversão e validação de tipos
        try:
            sensor_data = {
                'Coliformes': float(data['coliformes']),
                'pH': float(data['ph']),
                'DBO': float(data['dbo']),
                'NT': float(data['nt']),
                'FT': float(data['ft']),
                'Temperatura': float(data['temperatura']),
                'Turbidez': float(data['turbidez']),
                'Residuos': float(data['residuos']),
                'OD': float(data['od']),
            }
        except (ValueError, TypeError) as e:
            error_msg = f'Erro na conversão de dados: {str(e)}'
            esp_logger.error(f"Dispositivo {device_id}: {error_msg}")
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        # Log dos valores recebidos
        sensor_logger.info(f"Dados válidos recebidos do {device_id}:")
        for param, value in sensor_data.items():
            sensor_logger.info(f"  {param}: {value}")

        # Validações de range
        validation_errors = []

        if not (0 <= sensor_data['pH'] <= 14):
            validation_errors.append(
                f"pH fora do range (0-14): {sensor_data['pH']}")

        if sensor_data['Temperatura'] < -50 or sensor_data['Temperatura'] > 100:
            validation_errors.append(
                f"Temperatura fora do range (-50°C a 100°C): {sensor_data['Temperatura']}")

        if sensor_data['OD'] < 0:
            validation_errors.append(
                f"Oxigênio Dissolvido negativo: {sensor_data['OD']}")

        if validation_errors:
            for error in validation_errors:
                esp_logger.warning(f"Dispositivo {device_id}: {error}")
            return JsonResponse({
                'success': False,
                'error': 'Dados fora dos ranges válidos',
                'details': validation_errors
            }, status=400)

        # Verificar alertas
        check_sensor_alerts(sensor_data, device_id)

        # SALVAR DADOS EM MÚLTIPLAS FONTES
        save_operations = []

        # 1. Salvar no Firebase (prioridade)
        try:
            firebase_success = save_firebase_sensor_data(
                sensor_data, device_id)
            if firebase_success:
                sensor_logger.info(
                    f"Dados salvos no Firebase para {device_id}")
                save_operations.append("Firebase")
            else:
                sensor_logger.warning(
                    f"Falha ao salvar no Firebase para {device_id}")
        except Exception as firebase_error:
            sensor_logger.error(
                f"Erro Firebase para {device_id}: {firebase_error}")

        # 2. Salvar no banco de dados local (backup)
        try:
            from .models import SensorReading

            new_reading = SensorReading.objects.create(
                coliformes=sensor_data['Coliformes'],
                ph=sensor_data['pH'],
                dbo=sensor_data['DBO'],
                nt=sensor_data['NT'],
                ft=sensor_data['FT'],
                temperatura=sensor_data['Temperatura'],
                turbidez=sensor_data['Turbidez'],
                residuos=sensor_data['Residuos'],
                od=sensor_data['OD'],
                device_id=device_id
            )

            sensor_logger.info(
                f"Dados salvos no banco local: ID {new_reading.id}")
            save_operations.append("Database")

        except Exception as db_error:
            sensor_logger.error(f"Erro ao salvar no banco local: {db_error}")

        # 3. Salvar no cache
        cache.set('sensor_data', sensor_data, 300)
        cache.set(f'device_last_data_{device_id}', sensor_data, 600)
        save_operations.append("Cache")

        # Calcular IQA
        iqa_valor = None
        try:
            from .iqa_calculator import IQACalculator
            calculator = IQACalculator()
            iqa_valor, _ = calculator.calcular_IQA(sensor_data)

            iqa_logger.info(f"IQA calculado para {device_id}: {iqa_valor:.2f}")

            # Alert se IQA muito baixo
            if iqa_valor < 25:
                alert_logger.warning(
                    f"IQA crítico detectado no {device_id}: {iqa_valor:.2f}")

        except ImportError:
            iqa_logger.warning("IQACalculator não disponível")
        except Exception as iqa_error:
            iqa_logger.error(f"Erro no cálculo do IQA: {iqa_error}")

        # Resposta de sucesso
        response_data = {
            'success': True,
            'message': 'Dados recebidos e processados com sucesso',
            'timestamp': timezone.now().isoformat(),
            'device_id': device_id,
            'saved_to': save_operations
        }

        if iqa_valor is not None:
            response_data['iqa_calculado'] = round(iqa_valor, 2)

        esp_logger.info(
            f"Processamento concluído para {device_id}. Salvos em: {', '.join(save_operations)}")
        return JsonResponse(response_data)

    except json.JSONDecodeError as e:
        error_msg = f'JSON inválido: {str(e)}'
        esp_logger.error(f"Erro de parsing JSON de {client_ip}: {error_msg}")
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    except Exception as e:
        logger.error(f"Erro inesperado ao processar dados do ESP: {e}")
        esp_logger.error(f"Erro crítico no processamento: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)


def check_sensor_alerts(sensor_data, device_id):
    """
    Verifica e registra alertas baseados nos dados dos sensores
    """
    alerts = []

    # Alertas de pH
    if sensor_data['pH'] < 6.0:
        alerts.append(f"pH muito ácido: {sensor_data['pH']}")
    elif sensor_data['pH'] > 9.0:
        alerts.append(f"pH muito básico: {sensor_data['pH']}")

    # Alertas de temperatura
    if sensor_data['Temperatura'] > 35:
        alerts.append(f"Temperatura alta: {sensor_data['Temperatura']}°C")
    elif sensor_data['Temperatura'] < 5:
        alerts.append(f"Temperatura baixa: {sensor_data['Temperatura']}°C")

    # Alertas de oxigênio dissolvido
    if sensor_data['OD'] < 4:
        alerts.append(f"Oxigênio dissolvido baixo: {sensor_data['OD']} mg/L")

    # Alertas de turbidez
    if sensor_data['Turbidez'] > 40:
        alerts.append(f"Turbidez alta: {sensor_data['Turbidez']} NTU")

    # Alertas de coliformes
    if sensor_data['Coliformes'] > 80:
        alerts.append(
            f"Coliformes elevados: {sensor_data['Coliformes']} NMP/100mL")

    # Registrar alertas
    for alert in alerts:
        alert_logger.warning(f"ALERTA {device_id}: {alert}")

    if alerts:
        logger.info(f"Total de {len(alerts)} alertas gerados para {device_id}")


@csrf_exempt
@require_http_methods(["POST", "GET"])
def esp_heartbeat(request):
    """
    Endpoint para heartbeat com logging
    """
    client_ip = request.META.get('REMOTE_ADDR', 'Unknown')

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            device_id = data.get('device_id', 'Unknown')
            status = data.get('status', 'online')
            uptime = data.get('uptime', 0)

            esp_logger.info(
                f"Heartbeat de {device_id} (IP: {client_ip}): {status}, uptime: {uptime}ms")

            # Salvar status no cache
            cache.set(f'device_status_{device_id}', {
                'status': status,
                'last_seen': timezone.now().isoformat(),
                'uptime': uptime,
                'ip_address': client_ip
            }, 600)

            return JsonResponse({
                'success': True,
                'message': 'Heartbeat recebido',
                'server_time': timezone.now().isoformat()
            })

        except Exception as e:
            esp_logger.error(f"Erro no heartbeat de {client_ip}: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    else:  # GET
        esp_logger.debug(f"Ping recebido de {client_ip}")
        return JsonResponse({
            'success': True,
            'server_time': timezone.now().isoformat(),
            'message': 'Servidor online'
        })


def get_flood_risk_assessment(valores_sensores):
    """
    Avalia risco de enchente com logging
    """
    turbidez = valores_sensores.get('Turbidez', 0)
    residuos = valores_sensores.get('Residuos', 0)

    logger.debug(
        f"Avaliando risco de enchente: Turbidez={turbidez}, Resíduos={residuos}")

    if turbidez > 50 or residuos > 400:
        risk_level = "Risco Alto"
        css_class = "status-critical"
        alert_logger.warning(
            f"Risco alto de enchente detectado: Turbidez={turbidez}, Resíduos={residuos}")
    elif turbidez > 25 or residuos > 300:
        risk_level = "Risco Moderado"
        css_class = "status-warning"
        logger.info(
            f"Risco moderado de enchente: Turbidez={turbidez}, Resíduos={residuos}")
    else:
        risk_level = "Risco Baixo"
        css_class = "status-good"
        logger.debug("Risco baixo de enchente")

    return risk_level, css_class


def classify_iqa_from_value(iqa_valor):
    """Função auxiliar para classificar o IQA e obter a classe CSS."""
    if not isinstance(iqa_valor, (int, float)):
        return 'Inválido', 'status-critical'
    if iqa_valor > 80:  # Ajustado para IQA 0-100
        return 'Ótima', 'status-excellent'
    elif iqa_valor > 52:
        return 'Boa', 'status-good'
    elif iqa_valor > 37:
        return 'Regular', 'status-warning'
    elif iqa_valor > 20:
        return 'Ruim', 'status-bad'
    else:
        return 'Péssima', 'status-critical'


def get_flood_risk_assessment(valores_sensores):
    """Avalia risco de enchente com logging."""
    turbidez = valores_sensores.get('Turbidez', 0)
    residuos = valores_sensores.get('Residuos', 0)
    if turbidez > 50 or residuos > 400:
        return "Risco Alto", "status-critical"
    elif turbidez > 25 or residuos > 300:
        return "Risco Moderado", "status-warning"
    else:
        return "Risco Baixo", "status-good"


def dashboard(request):
    """
    View principal do dashboard com cálculo de IQA via IA.
    """
    try:
        valores_sensores = get_firebase_sensor_data()
        firebase_connected = firebase_service.test_connection()
        device_status = firebase_service.get_device_status("ESP32_SIMULATOR")
        latest_image_url = firebase_service.get_latest_image_url()
        data_source = 'firebase' if firebase_connected and valores_sensores else 'fallback'
        data_age = 'desconhecido'  # Valor padrão

        sensor_timestamp_str = valores_sensores.get('timestamp')
        last_update_obj = timezone.now() # Valor padrão
        if sensor_timestamp_str:
            try:
                last_update_obj = datetime.fromisoformat(sensor_timestamp_str)
            except (ValueError, TypeError):
                logger.warning(f"Não foi possível converter o timestamp '{sensor_timestamp_str}' para data.")

        # Lógica para data_age (opcional, pode ser baseada no mesmo objeto)
        if (timezone.now().replace(tzinfo=None) - last_update_obj.replace(tzinfo=None)).total_seconds() > 300:
            data_age = 'antigo'
        else:
            data_age = 'recente'

        # Prepara o dicionário com os valores de entrada para o modelo
        model_input = {
            'condutividade': valores_sensores.get('Condutividade', 15.0),
            'ph': valores_sensores.get('pH'),
            'temperatura': valores_sensores.get('Temperatura'),
            'turbidez': valores_sensores.get('Turbidez')
        }

        # USA O MODELO DE IA PARA PREDIZER O IQA
        iqa_valor = ml_predictor.predict_iqa_value(model_input)
        classificacao, css_class = classify_iqa_from_value(iqa_valor)

        flood_risk, flood_css = get_flood_risk_assessment(valores_sensores)

        context = {
            # Passa todos os valores (reais + padrão)
            'sensor_data': valores_sensores,
            'iqa': {'valor': round(iqa_valor, 2), 'classificacao': classificacao, 'css_class': css_class},
            'flood_risk': flood_risk,
            'latest_image_url': latest_image_url,
            'last_update': last_update_obj,
            'firebase_connected': firebase_connected,
            'data_source': data_source,  # Variável agora definida
            'device_status': device_status,  # Variável agora definida
            'data_age': data_age,
        }

        if request.user.is_authenticated:
            context.update({
                'user': request.user,
                'username': request.user.username,
                'email': request.user.email,
                'date_joined': request.user.date_joined,
                'last_login': request.user.last_login,
            })
            logger.debug(
                f"Dashboard carregado para usuário autenticado: {request.user.username}")

        logger.info(
            f"Dashboard renderizado com sucesso (fonte: {data_source})")
        return render(request, 'iotmonitor/dashboard.html', context)

    except Exception as e:
        logger.error(f"Erro crítico no dashboard: {e}", exc_info=True)
        context = {
            'error_message': 'Erro ao carregar dados dos sensores',
            'sensor_data': {},
            'iqa': {'valor': 0, 'classificacao': 'Erro', 'css_class': 'status-critical'},
        }
        return render(request, 'iotmonitor/dashboard.html', context)


def dashboard_api(request):
    """
    API do dashboard com cálculo de IQA via IA.
    """
    try:
        valores_sensores = get_firebase_sensor_data()
        latest_image_url = firebase_service.get_latest_image_url()

        model_input = {
            'condutividade': valores_sensores.get('Condutividade', 15.0),
            'ph': valores_sensores.get('pH'),
            'temperatura': valores_sensores.get('Temperatura'),
            'turbidez': valores_sensores.get('Turbidez')
        }

        # USA O MODELO DE IA PARA PREDIZER O IQA
        iqa_valor = ml_predictor.predict_iqa_value(model_input)
        classificacao, css_class = classify_iqa_from_value(iqa_valor)
        flood_risk, flood_css = get_flood_risk_assessment(valores_sensores)
        device_status = firebase_service.get_device_status("ESP32_SIMULATOR")

        data = {
            'success': True,
            'timestamp': valores_sensores.get('timestamp'),
            'sensor_data': {
                'temperatura': valores_sensores.get('Temperatura'),
                'ph': valores_sensores.get('pH'),
                'oxigenio': valores_sensores.get('OD'),
                'dbo': valores_sensores.get('DBO'),
                'coliformes': valores_sensores.get('Coliformes'),
                'nitrogenio': valores_sensores.get('NT'),
                'fosforo': valores_sensores.get('FT'),
                'turbidez': valores_sensores.get('Turbidez'),
                'solidos': valores_sensores.get('Residuos')
            },
            'iqa': {'valor': round(iqa_valor, 2), 'classificacao': classificacao, 'css_class': css_class},
            'flood_risk': {'level': flood_risk, 'css_class': flood_css},
            'device_status': device_status,
            'latest_image_url': latest_image_url
        }
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Erro na API do dashboard: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_sensor_values(request):
    """
    View para atualizar valores dos sensores (para testes ou integração)
    Apenas para desenvolvimento - remover em produção
    """
    try:
        data = json.loads(request.body)

        # Aqui você implementaria a lógica para salvar novos valores
        # Por exemplo, salvando em um modelo Django

        # Exemplo de como seria:
        # from .models import SensorReading
        #
        # new_reading = SensorReading(
        #     coliformes=data.get('coliformes'),
        #     ph=data.get('ph'),
        #     dbo=data.get('dbo'),
        #     # ... outros campos
        #     timestamp=timezone.now()
        # )
        # new_reading.save()

        logger.info(f"Valores de sensores atualizados: {data}")
        return JsonResponse({'success': True, 'message': 'Valores atualizados'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao atualizar sensores: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def firebase_test(request):
    """
    View para testar a conexão com Firebase
    Útil para debug em produção
    """
    try:
        test_results = {
            'timestamp': timezone.now().isoformat(),
            'firebase_initialized': firebase_service.initialized,
            'firebase_connected': firebase_service.is_connected() if firebase_service.initialized else False,
            'database_url': getattr(settings, 'FIREBASE_DATABASE_URL', 'Not configured'),
            'credentials_source': 'JSON' if getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None) else 'FILE' if getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None) else 'NONE',
            'debug_mode': settings.DEBUG
        }

        # Tentar obter dados de teste
        if firebase_service.initialized:
            try:
                test_data = firebase_service.get_sensor_data("ESP32_001")
                test_results['test_data_available'] = test_data is not None
                test_results['test_data_timestamp'] = test_data.get(
                    'timestamp') if test_data else None

                # Tentar obter dispositivos
                devices = firebase_service.get_all_devices()
                test_results['devices_found'] = len(devices) if devices else 0
                test_results['device_list'] = list(
                    devices.keys()) if devices else []

            except Exception as e:
                test_results['firebase_error'] = str(e)

        # Log dos resultados
        firebase_logger.info(f"Teste Firebase executado: {test_results}")

        return JsonResponse({
            'success': True,
            'results': test_results
        })

    except Exception as e:
        logger.error(f"Erro no teste Firebase: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def firebase_sync_data(request):
    """
    View para sincronizar dados entre banco local e Firebase
    """
    try:
        if not firebase_service.initialized:
            return JsonResponse({
                'success': False,
                'error': 'Firebase não inicializado'
            }, status=503)

        # Obter dados mais recentes do banco local
        from .models import SensorReading
        recent_readings = SensorReading.objects.order_by('-timestamp')[:10]

        synced_count = 0
        errors = []

        for reading in recent_readings:
            sensor_data = {
                'Coliformes': reading.coliformes,
                'pH': reading.ph,
                'DBO': reading.dbo,
                'NT': reading.nt,
                'FT': reading.ft,
                'Temperatura': reading.temperatura,
                'Turbidez': reading.turbidez,
                'Residuos': reading.residuos,
                'OD': reading.od,
            }

            try:
                if save_firebase_sensor_data(sensor_data, reading.device_id):
                    synced_count += 1
                else:
                    errors.append(f"Falha ao sincronizar leitura {reading.id}")
            except Exception as e:
                errors.append(f"Erro na leitura {reading.id}: {str(e)}")

        return JsonResponse({
            'success': True,
            'synced_count': synced_count,
            'total_readings': len(recent_readings),
            'errors': errors
        })

    except Exception as e:
        logger.error(f"Erro na sincronização Firebase: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def historical_data_api(request, sensor_parameter: str):
    """
    API que retorna dados históricos para um parâmetro de sensor específico.
    """
    # Mapeia o nome do parâmetro da URL para a chave no nosso dicionário de dados
    PARAM_MAP = {
        'temperatura': 'Temperatura',
        'ph': 'pH',
        'oxigenio': 'OD',
        'dbo': 'DBO',
        'coliformes': 'Coliformes',
        'nitrogenio': 'NT',
        'fosforo': 'FT',
        'turbidez': 'Turbidez',
        'solidos': 'Residuos'
    }

    data_key = PARAM_MAP.get(sensor_parameter.lower())
    if not data_key:
        return JsonResponse({'success': False, 'error': 'Parâmetro de sensor inválido'}, status=400)

    # Busca todo o histórico de leituras
    all_leituras = get_all_firebase_leituras()

    if not all_leituras:
        return JsonResponse({'success': False, 'error': 'Nenhum dado histórico encontrado'}, status=404)

    # Extrai os dados para o gráfico (labels e valores)
    labels = []
    data_points = []

    # Ordena por data
    for leitura in sorted(all_leituras, key=lambda x: x['timestamp']):
        # Formata o timestamp para exibir apenas a hora no gráfico
        timestamp_obj = datetime.fromisoformat(leitura['timestamp'])
        labels.append(timestamp_obj.strftime('%H:%M:%S'))

        # Pega o valor do sensor solicitado
        data_points.append(leitura.get(data_key))

    response_data = {
        'success': True,
        'labels': labels,
        'data': data_points
    }
    return JsonResponse(response_data)


# --- NOVA VIEW PARA RECEBER DADOS E IMAGEM DO ESP32-CAM ---
@csrf_exempt  # Essencial para permitir POSTs de dispositivos como o ESP32
def api_leitura_com_imagem(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)

    try:
        # 1. Pega os dados dos sensores (que virão como texto no corpo do POST)
        sensor_data_str = request.POST.get('sensor_data')
        if not sensor_data_str:
            return JsonResponse({'success': False, 'error': 'Dados do sensor ausentes'}, status=400)

        sensor_data = json.loads(sensor_data_str)

        # 2. Pega a imagem, se ela foi enviada
        imagem_file = request.FILES.get('image_file')
        image_url = None

        if imagem_file:
            # Salva o arquivo temporariamente
            temp_file_name = default_storage.save(
                imagem_file.name, imagem_file)
            temp_file_path = default_storage.path(temp_file_name)

            # Cria um nome único para o arquivo no Storage usando o timestamp
            timestamp_str = sensor_data.get(
                'timestamp', datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
            destination_name = f'leituras/{timestamp_str}.jpg'

            # 3. Faz o upload para o Firebase Storage
            image_url = firebase_service.upload_image_to_storage(
                temp_file_path, destination_name)

            # Limpa o arquivo temporário
            os.remove(temp_file_path)

            if image_url:
                # 4. Adiciona a URL da imagem aos dados do sensor
                sensor_data['imageUrl'] = image_url
            else:
                logger.warning(
                    "Falha ao fazer upload da imagem para o Storage.")

        # 5. Salva o registro completo (com ou sem URL) no Realtime Database
        # (Esta função será adicionada ao firebase_service.py a seguir)
        success, leitura_id = firebase_service.save_leitura_to_rtdb(
            sensor_data)

        if success:
            return JsonResponse({'success': True, 'message': 'Leitura recebida com sucesso', 'leitura_id': leitura_id})
        else:
            return JsonResponse({'success': False, 'error': 'Falha ao salvar no Realtime Database'}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON de dados do sensor inválido'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado na API de leitura: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Erro interno do servidor'}, status=500)
