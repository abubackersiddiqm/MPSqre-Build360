import uuid

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.files.application.services import (
    finalize_upload,
    governed_download_url,
    initiate_upload,
)
from modules.files.models import FileObject, FileVersion
from modules.platform.audit import AuditRecord, append_audit, request_metadata
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import UploadInitiateSerializer


def _file_response(file_object: FileObject, version: FileVersion) -> dict[str, object]:
    return {
        "file_public_id": str(file_object.public_id),
        "version_public_id": str(version.public_id),
        "version": version.version,
        "purpose_code": file_object.purpose_code,
        "data_class": file_object.data_class,
        "status": file_object.status,
        "upload_status": version.upload_status,
        "scan_status": version.scan_status,
        "original_name": version.original_name,
        "content_type": version.content_type,
        "size_bytes": version.actual_size_bytes or version.expected_size_bytes,
        "created_at": version.created_at.isoformat(),
    }


class UploadInitiateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("files.upload")
        serializer = UploadInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        try:
            grant = initiate_upload(
                company=self.tenant_context.company,
                purpose_code=serializer.validated_data["purpose_code"],
                data_class=serializer.validated_data["data_class"],
                original_name=serializer.validated_data["original_name"],
                content_type=serializer.validated_data["content_type"],
                size_bytes=serializer.validated_data["size_bytes"],
                sha256=serializer.validated_data["sha256"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        body = _file_response(grant.file_object, grant.file_version)
        body.update(
            {
                "upload_url": grant.upload_url,
                "upload_headers": {
                    "Content-Type": grant.file_version.content_type,
                    "x-amz-meta-sha256": grant.file_version.expected_sha256,
                },
                "expires_in_seconds": grant.expires_in_seconds,
            }
        )
        return Response(body, status=201)


class UploadFinalizeView(TenantScopedAPIView):
    def post(self, request: Request, version_id: uuid.UUID) -> Response:
        self.tenant_context.require("files.upload")
        request_id, _, _ = request_metadata(request._request)
        try:
            version = finalize_upload(
                version_public_id=version_id,
                company=self.tenant_context.company,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(_file_response(version.file_object, version))


class FileDetailView(TenantScopedAPIView):
    def get(self, request: Request, file_id: uuid.UUID) -> Response:
        self.tenant_context.require("files.read")
        file_object = FileObject.objects.filter(
            public_id=file_id,
            company=self.tenant_context.company,
        ).first()
        if not file_object:
            raise NotFound("Resource not found")
        version = file_object.versions.order_by("-version").first()
        if not version:
            raise NotFound("Resource not found")
        return Response(_file_response(file_object, version))


class FileDownloadView(TenantScopedAPIView):
    def get(self, request: Request, file_id: uuid.UUID) -> Response:
        self.tenant_context.require("files.download")
        file_object = FileObject.objects.filter(
            public_id=file_id,
            company=self.tenant_context.company,
        ).first()
        if not file_object:
            raise NotFound("Resource not found")
        try:
            version, url = governed_download_url(file_object=file_object)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        request_id, ip_address, user_agent = request_metadata(request._request)
        append_audit(
            AuditRecord(
                action="files.download.granted",
                entity_type="file_version",
                entity_public_id=version.public_id,
                actor_public_id=self.tenant_context.principal.user.public_id,
                company_public_id=self.tenant_context.company.public_id,
                request_id=request_id,
                correlation_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                after={"expires_in_seconds": settings.FILE_DOWNLOAD_URL_TTL_SECONDS},
            )
        )
        return Response(
            {
                "download_url": url,
                "expires_in_seconds": settings.FILE_DOWNLOAD_URL_TTL_SECONDS,
            }
        )
