import hashlib
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import Now

from kitsune.products.models import Topic
from kitsune.wiki.models import Document, HelpfulVote


def topics_for(product, parent=False):
    """Returns a list of topics that apply to passed in product.

    :arg product: a Product instance
    :arg parent: (optional) limit to topics with the given parent
    """

    docs = Document.objects.filter(
        locale=settings.WIKI_DEFAULT_LANGUAGE,
        is_archived=False,
        current_revision__isnull=False,
        products=product,
        category__in=settings.IA_DEFAULT_CATEGORIES,
    )

    qs = Topic.objects.filter(product=product)
    qs = qs.filter(visible=True, document__in=docs).annotate(num_docs=Count("document")).distinct()

    if parent or parent is None:
        qs = qs.filter(parent=parent)

    return qs


def documents_for(locale, topics=None, products=None, current_document=None):
    """Returns a tuple of lists of articles that apply to topics and products.

    The first item in the tuple is the list of articles for the locale
    specified. The second item is the list of fallback articles in en-US
    that aren't localized to the specified locale. If the specified locale
    is en-US, the second item will be None.

    :arg locale: the locale
    :arg topics: (optional) a list of Topic instances
    :arg products: (optional) a list of Product instances
    :arg current_document: (optional) a Document instance to exclude from the results

    The articles are returned as a list of dicts with the following keys:
        id
        document_title
        url
        document_parent_id
    """
    documents = _documents_for(locale, topics, products)

    if exclude_current_document := isinstance(current_document, Document):
        if documents and current_document.locale == locale:
            documents = [d for d in documents if d["id"] != current_document.id]

    # For locales that aren't en-US, get the en-US documents
    # to fill in for untranslated articles.
    if locale != settings.WIKI_DEFAULT_LANGUAGE:
        # Start by getting all of the English documents for the given products and topics.
        en_documents = _documents_for(
            locale=settings.WIKI_DEFAULT_LANGUAGE,
            products=products,
            topics=topics,
        )
        # Exclude the English versions of the translated documents we've already found.
        exclude_en_document_ids = set(
            d["document_parent_id"] for d in documents if "document_parent_id" in d
        )
        if exclude_current_document:
            # Exclude the current document if it's in English, or its parent if it's not.
            exclude_en_document_ids.add(
                current_document.parent.id if current_document.parent else current_document.id
            )
        fallback_documents = [d for d in en_documents if d["id"] not in exclude_en_document_ids]
    else:
        fallback_documents = None

    return documents, fallback_documents


def _documents_for(locale, topics=None, products=None):
    """Returns a list of articles that apply to passed in locale, topics and products."""
    # First try to get the results from the cache
    cache_key = _cache_key(locale, topics, products)
    documents_cache_key = f"documents_for:{cache_key}"
    documents = cache.get(documents_cache_key)
    if documents is not None:
        return documents

    qs = Document.objects.filter(
        locale=locale,
        is_archived=False,
        current_revision__isnull=False,
        category__in=settings.IA_DEFAULT_CATEGORIES,
    )
    # speed up query by removing any ordering, since we're doing it in python:
    qs = qs.select_related("current_revision", "parent").order_by()

    for topic in topics or []:
        # we need to filter against parent topics for localized articles
        qs = qs.filter(Q(topics=topic) | Q(parent__topics=topic))
    for product in products or []:
        # we need to filter against parent products for localized articles
        qs = qs.filter(Q(products=product) | Q(parent__products=product))
    qs = qs.distinct()

    votes_cache_key = f"votes_for:{cache_key}"
    votes_dict = cache.get(votes_cache_key)
    if votes_dict is None:
        # NOTE: It's important to use "created__range" rather than "created__gt"
        #       with Postgres, otherwise it won't use the index on the "created"
        #       field, and the "HelpfulVote" query will be massively slower.
        votes_query = (
            HelpfulVote.objects.filter(
                revision_id__in=qs.values_list("current_revision_id", flat=True),
                created__range=(datetime.now() - timedelta(days=30), Now()),
                helpful=True,
            )
            .values("revision_id")
            .annotate(count=Count("*"))
            .values("revision_id", "count")
        )
        votes_dict = {row["revision_id"]: row["count"] for row in votes_query}
        # the votes query is rather expensive, and only used for ordering,
        # so we can cache it rather aggressively
        cache.set(votes_cache_key, votes_dict, timeout=settings.CACHE_LONG_TIMEOUT)

    doc_dicts = []
    for d in qs:
        doc_dicts.append(
            dict(
                id=d.id,
                document_title=d.title,
                url=d.get_absolute_url(),
                document_parent_id=d.parent_id,
                document_summary=d.current_revision.summary,
                display_order=d.original.display_order,
                helpful_votes=votes_dict.get(d.current_revision_id, 0),
            )
        )

    # sort the results by ascending display_order and descending votes
    doc_dicts.sort(key=lambda x: (x["display_order"], -x["helpful_votes"]))

    cache.set(documents_cache_key, doc_dicts)
    return doc_dicts


def _cache_key(locale, topics, products):
    m = hashlib.md5()
    key = "{locale}:{topics}:{products}:new".format(
        locale=locale,
        topics=",".join(sorted([t.slug for t in topics or []])),
        products=",".join(sorted([p.slug for p in products or []])),
    )

    m.update(key.encode())
    return m.hexdigest()
