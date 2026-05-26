{{ config(materialized='table') }}

select distinct on (content_hash)
    id,
    source,
    transaction_date,
    post_date,
    description,
    original_description,
    category,
    category_overridden,
    transaction_type,
    amount,
    memo,
    running_balance,
    bill_id,
    imported_at,
    content_hash
from {{ source('budgetlens', 'transactions') }}
order by content_hash, imported_at desc
