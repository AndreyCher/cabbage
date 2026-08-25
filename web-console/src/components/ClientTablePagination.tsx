import { useEffect, useMemo, useState } from 'react'
import { TablePagination } from '@mui/material'

const pageSizeOptions = [25, 50, 100, 150]

export function useClientPagination<T>(items: T[]) {
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))

  useEffect(() => {
    if (page >= pageCount) setPage(pageCount - 1)
  }, [page, pageCount])

  const pageItems = useMemo(
    () => items.slice(page * pageSize, page * pageSize + pageSize),
    [items, page, pageSize],
  )

  return { page, pageSize, pageItems, setPage, setPageSize }
}

type ClientTablePaginationProps = {
  count: number
  page: number
  pageSize: number
  setPage: (page: number) => void
  setPageSize: (pageSize: number) => void
}

export function ClientTablePagination({ count, page, pageSize, setPage, setPageSize }: ClientTablePaginationProps) {
  return <TablePagination
    component="div"
    count={count}
    page={page}
    rowsPerPage={pageSize}
    rowsPerPageOptions={pageSizeOptions}
    onPageChange={(_event, nextPage) => setPage(nextPage)}
    onRowsPerPageChange={(event) => { setPageSize(Number(event.target.value)); setPage(0) }}
    labelRowsPerPage="Items per page:"
    showFirstButton
    showLastButton
  />
}
