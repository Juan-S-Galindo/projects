select * from {{ source('chase_transactions', 'chase_transactions') }}
