{{ config(materialized='table') }}

select
    *
from {{ ref('chase') }}
where bill_type is not null
