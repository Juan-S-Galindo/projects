select
	*
from
	{{ ref('bank_of_america') }}
where bill_type is not NULL
