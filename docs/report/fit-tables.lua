-- Table + inline-code handling for the documentation PDF build.
--
-- (1) Table: give every table content-proportional wrapping columns that sum to
--     the text width, so wide source tables (ARCHITECTURE / docs/live) wrap
--     instead of overflowing the right margin in the PDF.
-- (2) Code: pandoc renders inline code as `\texttt{...}`, which does NOT break --
--     a long identifier (ABILITY_REGISTRY, beast/skyborn/...) wider than its
--     column overprints the next column. Insert `\allowbreak` after `_` and `/`
--     so long ids wrap inside narrow cells. Additive (only adds break points),
--     so it never changes layout unless a token would otherwise overflow.
--
-- The filter runs top-down so the Table width pass measures the ORIGINAL code
-- text (via stringify) before Code rewrites it to raw LaTeX.

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

local function Table(tbl)
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

local function tex_escape(s)
  return (s:gsub('.', function(c)
    local m = {
      ['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}',
      ['$'] = '\\$', ['&'] = '\\&', ['#'] = '\\#', ['%'] = '\\%',
      ['_'] = '\\_', ['~'] = '\\textasciitilde{}', ['^'] = '\\textasciicircum{}',
    }
    return m[c] or c
  end))
end

local function Code(el)
  local esc = tex_escape(el.text)
  esc = esc:gsub('\\_', '\\_\\allowbreak{}')  -- break after SNAKE_CASE underscores
  esc = esc:gsub('/', '/\\allowbreak{}')       -- break after path/kinship slashes
  return pandoc.RawInline('latex', '\\texttt{' .. esc .. '}')
end

return {
  { traverse = 'topdown', Table = Table, Code = Code },
}
