"""Weaviate Cloud client helpers for DocuMind semantic memory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

import weaviate
from weaviate.classes import config as wc
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter, MetadataQuery

from config import Config


EmbeddingFn = Callable[[Sequence[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True)
class SemanticNode:
	"""Normalized payload that is stored in Weaviate."""

	node_id: str
	doc_id: str
	page: int
	section: str
	type: str
	content: str
	embedding: Sequence[float] | None = None


class DocuMindWeaviateClient:
	"""Cloud-aware Weaviate wrapper for semantic node storage and hybrid retrieval."""

	def __init__(
		self,
		cluster_url: str | None = None,
		api_key: str | None = None,
		collection_name: str | None = None,
		embedding_model: str | None = None,
		embedding_fn: EmbeddingFn | None = None,
	) -> None:
		self.cluster_url = (cluster_url or Config.WEAVIATE_URL).strip()
		self.api_key = (api_key or Config.WEAVIATE_API_KEY).strip()
		self.collection_name = (collection_name or Config.WEAVIATE_COLLECTION_NAME).strip()
		self.embedding_model = (embedding_model or Config.WEAVIATE_EMBEDDING_MODEL).strip()
		self._client: weaviate.WeaviateClient | None = None
		self._embedding_fn = embedding_fn
		self._embedder = None

	def connect(self) -> weaviate.WeaviateClient:
		"""Connect to the configured Weaviate Cloud cluster."""

		if self._client is not None:
			return self._client

		if not self.cluster_url:
			raise ValueError("WEAVIATE_URL must point to a Weaviate Cloud cluster URL.")
		if not self.api_key:
			raise ValueError("WEAVIATE_API_KEY is required to connect to Weaviate Cloud.")

		self._client = weaviate.connect_to_weaviate_cloud(
			cluster_url=self.cluster_url,
			auth_credentials=Auth.api_key(self.api_key),
		)
		return self._client

	def close(self) -> None:
		"""Close the underlying client connection."""

		if self._client is not None:
			self._client.close()
			self._client = None

	@property
	def client(self) -> weaviate.WeaviateClient:
		return self.connect()

	def ensure_schema(self) -> None:
		"""Create the semantic node collection if it does not exist yet."""

		client = self.client

		
		existing = client.collections.list_all()
		if self.collection_name in existing:
			return


		client.collections.create(
			name=self.collection_name,
			vectorizer_config=wc.Configure.Vectorizer.none(),
			properties=[
				wc.Property(name="node_id", data_type=wc.DataType.TEXT),
				wc.Property(name="doc_id", data_type=wc.DataType.TEXT),
				wc.Property(name="page", data_type=wc.DataType.INT),
				wc.Property(name="section", data_type=wc.DataType.TEXT),
				wc.Property(name="type", data_type=wc.DataType.TEXT),
				wc.Property(name="content", data_type=wc.DataType.TEXT),
			],
		)

	def _get_collection(self):
		self.ensure_schema()
		return self.client.collections.get(self.collection_name)

	def _embed_texts(self, texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
		if self._embedding_fn is not None:
			return [list(vector) for vector in self._embedding_fn(texts)]

		if self._embedder is None:
			try:
				from sentence_transformers import SentenceTransformer
			except ImportError as exc:
				raise RuntimeError(
					"sentence-transformers is required for BGE-small-en-v1.5 embeddings."
				) from exc

			self._embedder = SentenceTransformer(self.embedding_model)

		vectors: list[list[float]] = []
		text_list = list(texts)
		for start in range(0, len(text_list), batch_size):
			batch = text_list[start:start + batch_size]
			embeddings = self._embedder.encode(batch, normalize_embeddings=True)
			if hasattr(embeddings, "tolist"):
				vectors.extend([list(vector) for vector in embeddings.tolist()])
			else:
				vectors.extend([list(vector) for vector in embeddings])

		return vectors

	def _node_uuid(self, node: SemanticNode) -> str:
		raw_key = f"{node.doc_id}:{node.node_id}:{node.page}:{node.type}"
		return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_key))

	def _normalize_node(self, node: Mapping[str, Any] | SemanticNode) -> SemanticNode:
		if isinstance(node, SemanticNode):
			return node

		node_id = node.get("node_id") or node.get("id")
		required_fields = {
			"node_id": node_id,
			"doc_id": node.get("doc_id"),
			"page": node.get("page"),
			"type": node.get("type"),
			"content": node.get("content"),
		}
		missing = [name for name, value in required_fields.items() if value in (None, "")]
		if missing:
			raise ValueError(f"SemanticNode is missing required fields: {', '.join(missing)}")

		page = required_fields["page"]
		if isinstance(page, bool) or not isinstance(page, int) or page < 1:
			raise ValueError("SemanticNode.page must be a positive integer")

		return SemanticNode(
			node_id=str(node_id),
			doc_id=str(required_fields["doc_id"]),
			page=int(page),
			section=str(node.get("section", "")),
			type=str(required_fields["type"]),
			content=str(required_fields["content"]),
			embedding=node.get("embedding"),
		)

	def upsert_nodes(self, nodes: Iterable[Mapping[str, Any] | SemanticNode]) -> list[str]:
		"""Insert or replace semantic nodes in Weaviate."""

		normalized_nodes = [self._normalize_node(node) for node in nodes]
		if not normalized_nodes:
			return []

		collection = self._get_collection()
		embeddings_to_generate = [node.content for node in normalized_nodes if node.embedding is None]
		generated_embeddings: list[list[float]] = []
		if embeddings_to_generate:
			generated_embeddings = self._embed_texts(embeddings_to_generate)

		generated_index = 0
		stored_ids: list[str] = []

		for node in normalized_nodes:
			embedding = node.embedding
			if embedding is None:
				embedding = generated_embeddings[generated_index]
				generated_index += 1

			properties = {
				"node_id": node.node_id,
				"doc_id": node.doc_id,
				"page": node.page,
				"section": node.section,
				"type": node.type,
				"content": node.content,
			}

			object_id = self._node_uuid(node)

			if collection.data.exists(object_id):
				collection.data.replace(
					uuid=object_id,
					properties=properties,
					vector=list(embedding),
				)
				stored_ids.append(str(object_id))
			else:
				result = collection.data.insert(
					properties=properties,
					vector=list(embedding),
					uuid=object_id,
				)
				stored_ids.append(str(result))

		return stored_ids

	def hybrid_search(
		self,
		query: str,
		limit: int = 2,
		doc_id: str | None = None,
		node_type: str | None = None,
		page: int | None = None,
		alpha: float = 0.5,
	) -> list[dict[str, Any]]:
		"""Run hybrid vector + keyword retrieval with optional metadata filters."""

		collection = self._get_collection()
		filters = []
		if doc_id:
			filters.append(Filter.by_property("doc_id").equal(doc_id))
		if node_type:
			filters.append(Filter.by_property("type").equal(node_type))
		if page is not None:
			filters.append(Filter.by_property("page").equal(page))

		filter_expression = None
		if filters:
			filter_expression = filters[0]
			for extra_filter in filters[1:]:
				filter_expression = filter_expression & extra_filter

		query_vector = self._embed_texts([query])[0]

		results = collection.query.hybrid(
			query=query,
			vector=query_vector,
			limit=limit,
			alpha=alpha,
			filters=filter_expression,
			return_metadata=MetadataQuery(score=True),
		)

		items: list[dict[str, Any]] = []
		for obj in results.objects:
			properties = dict(obj.properties or {})
			metadata = obj.metadata
			if metadata is not None and hasattr(metadata, "score"):
				properties["score"] = metadata.score
			if hasattr(obj, "uuid"):
				properties["uuid"] = str(obj.uuid)
			items.append(properties)

		return items

