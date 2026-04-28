select
	*
from
	{{ ref('chase_bills_monthly_avg') }}
union all
select
	*
from
	{{ ref('bank_of_america_bills_monthly_avg') }}
