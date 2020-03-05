import random

from django.http import HttpResponse
from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from Lshopping.libs.captcha.captcha import captcha

# Create your views here.
from Lshopping.utils.yuntongxun.sms import CCP
from celery_tasks.sms import tasks
from . import constants
from . import serializers
import logging



logger = logging.getLogger('django')

# url('^image_codes/(?P<image_code_id>[\w-]+)/$', views.ImageCodeView.as_view()),
class ImageCodeView(APIView):

    def get(self, request, image_code_id):
        # 生成图片验证码
        # 保存图片验证码
        # 返回图片验证码到前端
        text , image = captcha.generate_captcha()
        redis_conn = get_redis_connection("verify_codes")
        redis_conn.setex("img_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        # 固定返回验证码图片数据，不需要REST framework框架的Response帮助我们决定返回响应数据的格式
        # 所以此处直接使用Django原生的HttpResponse即可
        return HttpResponse(image, content_type="images/jpg")


# url('^sms_codes/(?P<mobile>1[3-9]\d{9})/$', views.SMSCodeView.as_view()),
class SMSCodeView(GenericAPIView):
    """
    短信验证码
    传入参数：
        mobile, image_code_id, text
    """
    serializer_class = serializers.ImageCodeCheckSerializer

    def get(self, request, mobile):
        """
        创建短信验证码
        """
        # 判断图片验证码, 判断是否在60s内
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        # 生成短信验证码
        sms_code = "%06d" % random.randint(0, 999999)

        # 保存短信验证码与发送记录
        redis_conn = get_redis_connection('verify_codes')
        pl = redis_conn.pipeline()
        pl.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
        pl.execute()

        # 发送短信验证码
        # sms_code_expires = str(constants.SMS_CODE_REDIS_EXPIRES // 60)
        # ccp = CCP()
        # ccp.send_template_sms(mobile, [sms_code, sms_code_expires], constants.SMS_CODE_TEMP_ID)
        # try:
        #     ccp = CCP()
        #     result = ccp.send_template_sms(mobile, [sms_code, sms_code_expires], constants.SMS_CODE_TEMP_ID)
        # except Exception as e:
        #     logger.error("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
        #     return Response({"message": "failed"}, status = status.HTTP_503_SERVICE_UNAVAILABLE)
        # else:
        #     if result == 0:
        #         logger.info("发送验证码短信[正常][ mobile: %s ]" % mobile)
        #         return Response({"message": "OK"})
        #     else:
        #         logger.warning("发送验证码短信[失败][ mobile: %s ]" % mobile)
        #         return Response({"message": "failed"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        # 发送短信验证码
        sms_code_expires = str(constants.SMS_CODE_REDIS_EXPIRES // 60)
        temp_id = constants.SMS_CODE_TEMP_ID
        tasks.send_sms_code.delay(mobile, sms_code, sms_code_expires, temp_id)

        return Response({"message": "OK"})







