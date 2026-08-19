# Infrastructure boundary

Compose is for local development and integration testing. Production requires
managed credentials, TLS at the approved edge, immutable image digests,
separate environments, backup and restoration evidence, deployment health
gates, and an approved secret manager.

The current MinIO image is a local-development dependency only. Production
object storage must use the approved R2-compatible abstraction and private
buckets.

