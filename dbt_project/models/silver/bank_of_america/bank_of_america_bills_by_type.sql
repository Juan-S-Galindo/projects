{{
    config(
        materialized='table'
    )
}}

with recurring_bills as (

    select
        bill_type,
        amount,
        transaction_date
    from {{ ref('bank_of_america_recurring_bills') }}

),

last_12_months as (

    select
        bill_type,
        amount,
        transaction_date
    from recurring_bills
    where transaction_date >= current_date - interval '12 months'

),

aggregated as (

    select
        bill_type,
        sum(amount)                                         as total_amount,
        count(*)                                            as transaction_count,
        min(transaction_date)                               as earliest_transaction_date,
        max(transaction_date)                               as latest_transaction_date
    from last_12_months
    group by bill_type

)

select * from aggregated
