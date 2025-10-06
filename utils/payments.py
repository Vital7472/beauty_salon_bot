"""
Модуль платежной инфраструктуры
Поддержка различных платежных систем
"""

import logging
import hashlib
import hmac
import json
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class PaymentProvider(Enum):
    """Доступные платежные провайдеры"""
    CASH = "cash"  # Наличные при получении
    TELEGRAM = "telegram"  # Telegram Payments (Stripe, ЮКassa и др.)
    YOOKASSA = "yookassa"  # Прямая интеграция с ЮКassa
    STRIPE = "stripe"  # Прямая интеграция со Stripe
    TINKOFF = "tinkoff"  # Тинькофф эквайринг
    SBERBANK = "sberbank"  # Сбербанк эквайринг


class PaymentStatus(Enum):
    """Статусы платежей"""
    PENDING = "pending"  # Ожидает оплаты
    PROCESSING = "processing"  # В процессе
    SUCCEEDED = "succeeded"  # Успешно
    FAILED = "failed"  # Ошибка
    CANCELLED = "cancelled"  # Отменен
    REFUNDED = "refunded"  # Возврат


class PaymentMethod(Enum):
    """Способы оплаты"""
    CARD = "card"  # Банковская карта
    CASH = "cash"  # Наличные
    SBP = "sbp"  # Система быстрых платежей
    YOOMONEY = "yoomoney"  # ЮMoney
    QIWI = "qiwi"  # QIWI кошелек
    BONUS = "bonus"  # Бонусы


class PaymentGateway:
    """Базовый класс для платежных шлюзов"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = None

    def create_payment(self, amount: int, description: str, order_id: str,
                      user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать платеж

        Args:
            amount: Сумма в копейках
            description: Описание платежа
            order_id: ID заказа
            user_data: Данные пользователя

        Returns:
            dict: {
                'payment_id': str,
                'payment_url': str,
                'status': str
            }
        """
        raise NotImplementedError

    def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Проверить статус платежа

        Args:
            payment_id: ID платежа

        Returns:
            dict: {
                'status': str,
                'paid': bool,
                'amount': int
            }
        """
        raise NotImplementedError

    def cancel_payment(self, payment_id: str) -> bool:
        """Отменить платеж"""
        raise NotImplementedError

    def refund_payment(self, payment_id: str, amount: Optional[int] = None) -> bool:
        """Вернуть платеж"""
        raise NotImplementedError

    def verify_webhook(self, data: Dict[str, Any], signature: str) -> bool:
        """Проверить подпись webhook"""
        raise NotImplementedError


class TelegramPaymentGateway(PaymentGateway):
    """
    Telegram Payments API
    Использует встроенные платежи Telegram (Stripe, ЮКassa и др.)
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = PaymentProvider.TELEGRAM
        self.provider_token = config.get('provider_token')

    def create_payment(self, amount: int, description: str, order_id: str,
                      user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать счет через Telegram Bot API

        Note: Фактически счет отправляется через bot.send_invoice()
        Здесь только подготовка данных
        """
        return {
            'payment_id': f'tg_{order_id}',
            'title': description,
            'description': description,
            'payload': order_id,
            'currency': 'RUB',
            'prices': [{'label': description, 'amount': amount}],
            'provider_token': self.provider_token,
            'need_phone_number': True,
            'need_email': False,
            'send_phone_number_to_provider': True
        }

    def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Проверка через webhook от Telegram
        """
        return {
            'status': PaymentStatus.PENDING.value,
            'paid': False,
            'message': 'Use webhook handler'
        }

    def verify_webhook(self, data: Dict[str, Any], signature: str = None) -> bool:
        """
        Telegram webhook не использует signature
        Проверяется через bot.get_updates()
        """
        return True


class YooKassaGateway(PaymentGateway):
    """
    ЮKassa (Яндекс.Касса) API v3
    https://yookassa.ru/developers/api
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = PaymentProvider.YOOKASSA
        self.shop_id = config.get('shop_id')
        self.secret_key = config.get('secret_key')
        self.return_url = config.get('return_url')
        self.api_url = 'https://api.yookassa.ru/v3'

    def create_payment(self, amount: int, description: str, order_id: str,
                      user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать платеж в ЮKassa

        Requires: yookassa library
        pip install yookassa
        """
        try:
            from yookassa import Configuration, Payment

            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key

            payment = Payment.create({
                "amount": {
                    "value": f"{amount / 100:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": self.return_url
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "order_id": order_id,
                    "user_id": user_data.get('user_id')
                },
                "receipt": {
                    "customer": {
                        "phone": user_data.get('phone')
                    },
                    "items": [{
                        "description": description,
                        "quantity": "1",
                        "amount": {
                            "value": f"{amount / 100:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1
                    }]
                }
            }, idempotency_key=order_id)

            return {
                'payment_id': payment.id,
                'payment_url': payment.confirmation.confirmation_url,
                'status': payment.status
            }

        except ImportError:
            logger.error("yookassa library not installed")
            return {'error': 'yookassa not configured'}
        except Exception as e:
            logger.error(f"YooKassa payment creation error: {e}")
            return {'error': str(e)}

    def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """Проверить статус платежа"""
        try:
            from yookassa import Configuration, Payment

            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key

            payment = Payment.find_one(payment_id)

            return {
                'status': payment.status,
                'paid': payment.paid,
                'amount': int(float(payment.amount.value) * 100)
            }
        except Exception as e:
            logger.error(f"YooKassa check error: {e}")
            return {'status': 'error', 'paid': False}

    def cancel_payment(self, payment_id: str) -> bool:
        """Отменить платеж"""
        try:
            from yookassa import Configuration, Payment

            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key

            Payment.cancel(payment_id)
            return True
        except Exception as e:
            logger.error(f"YooKassa cancel error: {e}")
            return False

    def refund_payment(self, payment_id: str, amount: Optional[int] = None) -> bool:
        """Возврат платежа"""
        try:
            from yookassa import Configuration, Refund

            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key

            refund_data = {"payment_id": payment_id}
            if amount:
                refund_data["amount"] = {
                    "value": f"{amount / 100:.2f}",
                    "currency": "RUB"
                }

            Refund.create(refund_data)
            return True
        except Exception as e:
            logger.error(f"YooKassa refund error: {e}")
            return False

    def verify_webhook(self, data: Dict[str, Any], signature: str) -> bool:
        """Проверить подпись webhook"""
        try:
            notification_data = json.dumps(data, separators=(',', ':'))
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                notification_data.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"YooKassa signature verification error: {e}")
            return False


class StripeGateway(PaymentGateway):
    """
    Stripe Payment Gateway
    https://stripe.com/docs/api
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = PaymentProvider.STRIPE
        self.secret_key = config.get('secret_key')
        self.webhook_secret = config.get('webhook_secret')

    def create_payment(self, amount: int, description: str, order_id: str,
                      user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать платеж через Stripe

        Requires: stripe library
        pip install stripe
        """
        try:
            import stripe

            stripe.api_key = self.secret_key

            # Создать PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='rub',
                description=description,
                metadata={
                    'order_id': order_id,
                    'user_id': user_data.get('user_id')
                },
                receipt_email=user_data.get('email')
            )

            return {
                'payment_id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status
            }

        except ImportError:
            logger.error("stripe library not installed")
            return {'error': 'stripe not configured'}
        except Exception as e:
            logger.error(f"Stripe payment creation error: {e}")
            return {'error': str(e)}

    def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """Проверить статус платежа"""
        try:
            import stripe

            stripe.api_key = self.secret_key
            intent = stripe.PaymentIntent.retrieve(payment_id)

            return {
                'status': intent.status,
                'paid': intent.status == 'succeeded',
                'amount': intent.amount
            }
        except Exception as e:
            logger.error(f"Stripe check error: {e}")
            return {'status': 'error', 'paid': False}

    def cancel_payment(self, payment_id: str) -> bool:
        """Отменить платеж"""
        try:
            import stripe

            stripe.api_key = self.secret_key
            stripe.PaymentIntent.cancel(payment_id)
            return True
        except Exception as e:
            logger.error(f"Stripe cancel error: {e}")
            return False

    def refund_payment(self, payment_id: str, amount: Optional[int] = None) -> bool:
        """Возврат платежа"""
        try:
            import stripe

            stripe.api_key = self.secret_key

            refund_data = {'payment_intent': payment_id}
            if amount:
                refund_data['amount'] = amount

            stripe.Refund.create(**refund_data)
            return True
        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return False

    def verify_webhook(self, payload: str, signature: str) -> bool:
        """Проверить подпись webhook"""
        try:
            import stripe

            stripe.api_key = self.secret_key
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except Exception as e:
            logger.error(f"Stripe signature verification error: {e}")
            return False


class PaymentManager:
    """Менеджер платежных систем"""

    def __init__(self):
        self.gateways = {}
        self._load_config()

    def _load_config(self):
        """Загрузить конфигурацию платежных систем"""
        try:
            from config import PAYMENT_CONFIG

            # Telegram Payments
            if PAYMENT_CONFIG.get('telegram'):
                self.gateways[PaymentProvider.TELEGRAM] = TelegramPaymentGateway(
                    PAYMENT_CONFIG['telegram']
                )

            # ЮKassa
            if PAYMENT_CONFIG.get('yookassa'):
                self.gateways[PaymentProvider.YOOKASSA] = YooKassaGateway(
                    PAYMENT_CONFIG['yookassa']
                )

            # Stripe
            if PAYMENT_CONFIG.get('stripe'):
                self.gateways[PaymentProvider.STRIPE] = StripeGateway(
                    PAYMENT_CONFIG['stripe']
                )

        except ImportError:
            logger.warning("PAYMENT_CONFIG not found in config.py")

    def get_gateway(self, provider: PaymentProvider) -> Optional[PaymentGateway]:
        """Получить платежный шлюз"""
        return self.gateways.get(provider)

    def create_payment(self, provider: PaymentProvider, amount: int,
                      description: str, order_id: str,
                      user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создать платеж"""
        gateway = self.get_gateway(provider)
        if not gateway:
            return {'error': f'Provider {provider.value} not configured'}

        return gateway.create_payment(amount, description, order_id, user_data)

    def get_available_methods(self) -> list:
        """Получить доступные способы оплаты"""
        methods = [PaymentMethod.CASH]  # Наличные всегда доступны

        if PaymentProvider.TELEGRAM in self.gateways:
            methods.append(PaymentMethod.CARD)

        if PaymentProvider.YOOKASSA in self.gateways:
            methods.extend([PaymentMethod.CARD, PaymentMethod.SBP, PaymentMethod.YOOMONEY])

        if PaymentProvider.STRIPE in self.gateways:
            methods.append(PaymentMethod.CARD)

        return list(set(methods))


# Глобальный менеджер платежей
payment_manager = PaymentManager()
