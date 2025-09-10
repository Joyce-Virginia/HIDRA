from django.urls import path
from . import views


urlpatterns = [
    # URLs principais
    path('', views.homepage, name='homepage'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # URLs de autenticação
    path('login/', views.login, name='login'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('logout/', views.logout_view, name='logout'),
    # URLs para recuperação de senha
    path('password_reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/complete/', views.password_reset_complete, name='password_reset_complete'),
    # URLs AJAX para validações
    path('check-username/', views.check_username, name='check_username'),
    path('check-email/', views.check_email, name='check_email'),
    # # API JSON para o dashboard (AJAX) com IQA
    path('dashboard_api/', views.dashboard_api, name='dashboard_api'),
    path('api/update-sensors/', views.update_sensor_values, name='update_sensors'),
    # Endpoint para testes (remover em produção)
    path('api/sensors/test/', views.update_sensor_values, name='update_sensor_values'),

    # APIs
    path('api/sensor-data/', views.esp_sensor_data, name='esp_sensor_data'),
    path('api/heartbeat/', views.esp_heartbeat, name='esp_heartbeat'),
    # Novas rotas para Firebase
    path('api/firebase-test/', views.firebase_test, name='firebase_test'),
    path('api/firebase-sync/', views.firebase_sync_data, name='firebase_sync'),
    path('api/historical_data/<str:sensor_parameter>/', views.historical_data_api, name='historical_data_api'),
    path('api/leitura-com-imagem/', views.api_leitura_com_imagem, name='api_leitura_com_imagem'),
]
