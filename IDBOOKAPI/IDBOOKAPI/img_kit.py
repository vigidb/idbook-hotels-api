# SDK initialization
from IDBOOKAPI.settings import IMAGEKIT_PUBLIC_KEY, IMAGEKIT_PRIVATE_KEY, IMAGEKIT_ENDPOINT
from imagekitio import ImageKit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage

imagekit = ImageKit(
    private_key=IMAGEKIT_PRIVATE_KEY,
    public_key=IMAGEKIT_PUBLIC_KEY,
    url_endpoint=IMAGEKIT_ENDPOINT
)


def upload_media_to_bucket(file_name, file_path, tags,):
    folder = '/hotels/'
    webhook_url = "https://www.idbookhotels.com/"
    # extensions = [
    #     {
    #         'name': 'google-auto-tagging',
    #         'minConfidence': 80,
    #         'maxTags': 10
    #     }
    # ]
    # options = UploadFileRequestOptions(
    #     use_unique_file_name=False,
    #     tags=tags,
    #     # folder=folder,
    #     is_private_file=False,
    #     # custom_coordinates='10,10,20,20',
    #     response_fields=['tags', 'custom_coordinates', 'is_private_file',
    #                      'embedded_metadata', 'custom_metadata'],
    #     extensions=extensions,
    #     webhook_url=webhook_url,
    #     overwrite_file=True,
    #     overwrite_ai_tags=False,
    #     overwrite_tags=False,
    #     overwrite_custom_metadata=True
    #
    # )
    fs = FileSystemStorage()
    saved_file_path = fs.save(file_name, file_path)
    response = imagekit.upload_file(
        file=open(fs.path(saved_file_path), "rb"),
        file_name=file_name,
        # options=options
    )
    return response.response_metadata.raw


class ImagekitioService(APIView):
    def post(self, request, *args, **kwargs):
        file_path = request.FILES.get('file_path')
        file_name = request.data.get('file_name')

        if not file_path or not file_name:
            return Response({'error': 'Both file_path and file_name are required'}, status=status.HTTP_400_BAD_REQUEST)

        fs = FileSystemStorage()
        saved_file_path = fs.save(file_name, file_path)

        response = imagekit.upload_file(
            file=open(fs.path(saved_file_path), "rb"),
            file_name=file_name,
        )

        return Response({
            'message': 'File uploaded successfully',
            'saved_file_path': saved_file_path,
            'response': response.response_metadata.raw
        }, status=status.HTTP_201_CREATED)
