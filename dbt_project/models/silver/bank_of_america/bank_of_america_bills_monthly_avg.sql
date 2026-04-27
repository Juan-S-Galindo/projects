{{ config(materialized='table') }}

with recurring_bills as (

    select
        bill_type,
        date_trunc('month', transaction_date) as month,
        amount
    from {{ ref('bank_of_america_recurring_bills') }}

),

aggregated as (

    select
        bill_type,
        month,
        sum(amount)                             as total_amount,
        count(*)                                as transaction_count,
        sum(amount) / count(*)                  as avg_amount_per_transaction
    from recurring_bills
    group by bill_type, month

)

select * from aggregated
