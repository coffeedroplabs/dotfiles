-- WSL clipboard provider: use Windows clip.exe (copy) + powershell (paste).
-- No package needed; works on any WSL install. cache_enabled = 0 because the
-- Windows clipboard can change outside nvim, so stale cache would paste wrong text.
if vim.fn.has('wsl') == 1 then
  vim.g.clipboard = {
    name = 'wsl-clipboard',
    copy = { ['+'] = 'clip.exe', ['*'] = 'clip.exe' },
    paste = {
      ['+'] = 'powershell.exe -NoProfile -Command Get-Clipboard',
      ['*'] = 'powershell.exe -NoProfile -Command Get-Clipboard',
    },
    cache_enabled = 0,
  }
end

local o = vim.opt
vim.g.mapleader = ' '          -- space is the leader key
o.expandtab = true             -- spaces, not tabs
o.shiftwidth = 2               -- 2 spaces per indent level
o.number = true                -- absolute number on the cursor line, relative elsewhere
o.relativenumber = true        -- relative line numbers for fast jumps
o.ignorecase = true            -- search is case-insensitive by default
o.smartcase = true             -- case-sensitive only if i type a capital
o.clipboard = 'unnamedplus'    -- share the system clipboard
o.scrolloff = 16               -- keep cursor away from the screen edge
o.undofile = true              -- persistent undo across sessions

