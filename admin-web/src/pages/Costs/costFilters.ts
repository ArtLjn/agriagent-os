import type { Dayjs } from 'dayjs';

import type { ListRecordsParams } from '../../api/costs';

export type MonthRange = [Dayjs, Dayjs] | null;

interface BuildCostListParamsOptions {
  selectedCycle?: number;
  page: number;
  size: number;
  monthRange?: MonthRange;
}

export function buildCostListParams({
  selectedCycle,
  page,
  size,
  monthRange,
}: BuildCostListParamsOptions): ListRecordsParams {
  const params: ListRecordsParams = { page, size };
  if (selectedCycle) params.cycle_id = selectedCycle;
  if (monthRange) {
    params.date_from = monthRange[0].startOf('month').format('YYYY-MM-DD');
    params.date_to = monthRange[1].endOf('month').format('YYYY-MM-DD');
  }
  return params;
}
