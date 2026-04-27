with source as (

    select * from {{ ref('bank_of_america_transactions') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by
                transaction_date,
                description,
                amount,
                running_balance,
                source
            order by ingested_at desc
        ) as row_num

    from source

),

filtered as (

    select
        id,
        transaction_date,
        description,
        amount,
        running_balance,
        source,
        ingested_at
    from deduplicated
    where row_num = 1

)

select * from filtered
