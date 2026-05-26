{{ config(materialized='table') }}

/*
  Canonical transaction table.

  Deduplication: one row per txn_hash (md5 of source|date|description|amount).
  Mutable attributes (category overrides, bill links) live in
  transaction_attributes and are applied here via LEFT JOIN.
  The raw staging category is the fallback when no override exists.
*/

with staged as (
    select distinct on (txn_hash)
        id,
        source,
        transaction_date,
        post_date,
        description,
        original_description,
        category        as raw_category,
        transaction_type,
        amount,
        memo,
        running_balance,
        imported_at,
        content_hash,
        txn_hash
    from {{ source('budgetlens', 'transactions') }}
    where txn_hash is not null
    order by txn_hash, imported_at desc
),

attrs as (
    select * from {{ source('budgetlens', 'transaction_attributes') }}
)

select
    s.id,
    s.source,
    s.transaction_date,
    s.post_date,
    s.description,
    s.original_description,
    coalesce(a.category, s.raw_category)        as category,
    coalesce(a.category_overridden, false)       as category_overridden,
    s.transaction_type,
    s.amount,
    s.memo,
    s.running_balance,
    a.bill_id,
    s.imported_at,
    s.content_hash,
    s.txn_hash
from staged s
left join attrs a on a.txn_hash = s.txn_hash
