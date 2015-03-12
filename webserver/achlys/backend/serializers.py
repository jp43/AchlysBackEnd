from django.contrib.auth.models import User
from rest_framework import serializers
from backend.models import Job


class JobSerializer(serializers.ModelSerializer):

    #author = serializers.SlugRelatedField(
    #    queryset=User.objects.filter(), slug_field='username'
    #)

    class Meta:
        model = Job
        fields = ('id', 'chem_lib_path', 'job_path', 'created_at')
