with source as (

    select * from {{ source('chase_transactions', 'chase_transactions') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by
                transaction_date,
                post_date,
                description,
                category,
                type,
                amount
            order by ingested_at desc
        ) as row_num

    from source

),

filtered as (

    select
        id,
        transaction_date,
        post_date,
        description,
        category,
        type,
        amount,
        memo,
        bill_type,
        ingested_at
    from deduplicated
    where row_num = 1

)

select * from filtered
