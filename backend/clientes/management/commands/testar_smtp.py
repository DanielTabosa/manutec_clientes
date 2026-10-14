from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

from clientes.preparacao import envio_configurado


class Command(BaseCommand):
    help = 'Envia uma mensagem simples de teste pela conta SMTP configurada, para um endereço informado.'

    def add_arguments(self, parser):
        parser.add_argument('--para', required=True, help='Endereço do próprio usuário para receber o teste.')

    def handle(self, *args, para, **options):
        if not envio_configurado():
            raise CommandError('Configure DJANGO_EMAIL_HOST e DJANGO_EMAIL_FROM no .env.')
        self.stdout.write(f'Servidor {settings.EMAIL_HOST}:{settings.EMAIL_PORT} ({"SSL" if settings.EMAIL_USE_SSL else "TLS" if settings.EMAIL_USE_TLS else "sem criptografia"}), remetente {settings.DEFAULT_FROM_EMAIL}.')
        try:
            EmailMessage('Teste de envio — Manutec Clientes',
                         'Mensagem de teste da configuração SMTP. Nenhum documento anexado.',
                         settings.DEFAULT_FROM_EMAIL, [para]).send()
        except Exception as exc:
            raise CommandError(f'Falha no envio: {type(exc).__name__}: {exc}')
        self.stdout.write(self.style.SUCCESS('Mensagem aceita pelo servidor SMTP. Confira a caixa de entrada (e o spam); aceitação não comprova entrega.'))
