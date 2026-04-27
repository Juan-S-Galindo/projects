select * from {{ source('bank_of_america_transactions', 'bank_of_america_transactions') }}
