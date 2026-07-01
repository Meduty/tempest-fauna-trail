-- Give every table content-proportional wrapping columns that sum to the text
-- width, so wide source tables (ARCHITECTURE / docs/live) wrap instead of
-- overflowing the right margin in the PDF.

local stringify = pandoc.utils.stringify

local function cell_len(cell)
  return #stringify(cell.contents)
end

local function scan(rows, maxlen)
  for _, row in ipairs(rows) do
    for i, cell in ipairs(row.cells) do
      local l = cell_len(cell)
      if maxlen[i] == nil or l > maxlen[i] then maxlen[i] = l end
    end
  end
end

function Table(tbl)
  local ncol = #tbl.colspecs
  local maxlen = {}
  scan(tbl.head.rows, maxlen)
  for _, body in ipairs(tbl.bodies) do
    scan(body.head, maxlen)
    scan(body.body, maxlen)
  end

  local total = 0
  for i = 1, ncol do
    local m = maxlen[i] or 4
    if m > 55 then m = 55 end   -- cap a runaway cell so others keep room
    if m < 4 then m = 4 end
    maxlen[i] = m
    total = total + m
  end

  for i = 1, ncol do
    tbl.colspecs[i] = { tbl.colspecs[i][1], maxlen[i] / total }
  end
  return tbl
end
