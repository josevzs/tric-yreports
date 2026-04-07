import { useState } from 'react';
import { patchExpenseCategory, applyCategorizations } from '../../api/client';
import { useAppStore } from '../../store/appStore';
import type { Expense, CategorySuggestion } from '../../types';
import './ExpenseTable.css';

export default function ExpenseTable() {
  const {
    sessionId, expenses, suggestions, allCategories,
    patchExpenseCategory: patchLocal, applyAllSuggestions, setStep,
  } = useAppStore();

  const [filterText, setFilterText] = useState('');
  const [filterCat, setFilterCat] = useState('');
  const [filterPayer, setFilterPayer] = useState('');
  const [filterConf, setFilterConf] = useState<'all' | 'high' | 'low'>('all');

  const suggestionMap = new Map<number, CategorySuggestion>(
    suggestions.map(s => [s.entry_id, s])
  );

  const payers = [...new Set(expenses.map(e => e.payer))];
  const uncategorized = expenses.filter(e => e.category === 'UNCATEGORIZED').length;
  const highConf = suggestions.filter(s => s.confidence >= 0.85).length;

  const filtered = expenses.filter(e => {
    if (filterText && !e.description.toLowerCase().includes(filterText.toLowerCase())) return false;
    if (filterCat && e.category !== filterCat) return false;
    if (filterPayer && e.payer !== filterPayer) return false;
    if (filterConf === 'high') {
      const s = suggestionMap.get(e.entry_id);
      if (!s || s.confidence < 0.85) return false;
    }
    if (filterConf === 'low') {
      const s = suggestionMap.get(e.entry_id);
      if (s && s.confidence >= 0.85) return false;
    }
    return true;
  });

  async function handleCategoryChange(expense: Expense, newCat: string) {
    if (!sessionId) return;
    patchLocal(expense.entry_id, newCat);
    await patchExpenseCategory(sessionId, expense.entry_id, newCat).catch(() => {
      patchLocal(expense.entry_id, expense.category);
    });
  }

  async function handleApplyAll() {
    if (!sessionId) return;
    const apps = applyAllSuggestions(0.85);
    if (apps.length) await applyCategorizations(sessionId, apps).catch(() => {});
  }

  return (
    <div className="expense-table-wrapper">
      {/* ── Toolbar ── */}
      <div className="et-toolbar">
        <div className="et-stats">
          <span className="et-stat">{expenses.length} expenses</span>
          {uncategorized > 0 && <span className="et-stat warn">{uncategorized} uncategorized</span>}
          {suggestions.length > 0 && <span className="et-stat info">{suggestions.length} suggestions</span>}
        </div>
        <div className="et-actions">
          {highConf > 0 && (
            <button className="btn btn-sm btn-fill" onClick={handleApplyAll}>
              Apply {highConf} (≥85%)
            </button>
          )}
          <button className="btn btn-sm" onClick={() => setStep('report')}>
            Generate Report →
          </button>
        </div>
      </div>

      {/* ── Filters ── */}
      <div className="et-filters">
        <input
          type="text"
          placeholder="Search description…"
          value={filterText}
          onChange={e => setFilterText(e.target.value)}
          className="et-filter-input"
        />
        <select value={filterCat} onChange={e => setFilterCat(e.target.value)} className="et-filter-select">
          <option value="">All categories</option>
          <option value="UNCATEGORIZED">— Uncategorized</option>
          {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterPayer} onChange={e => setFilterPayer(e.target.value)} className="et-filter-select">
          <option value="">All payers</option>
          {payers.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={filterConf} onChange={e => setFilterConf(e.target.value as typeof filterConf)} className="et-filter-select">
          <option value="all">All confidence</option>
          <option value="high">High ≥85%</option>
          <option value="low">Low / no suggestion</option>
        </select>
        <span className="et-count">{filtered.length}/{expenses.length}</span>
      </div>

      {/* ── Table ── */}
      <div className="et-scroll">
        <table className="et-table">
          <thead>
            <tr>
              <th>DATE</th>
              <th>DESCRIPTION</th>
              <th className="num">AMOUNT</th>
              <th>PAYER</th>
              <th>CATEGORY</th>
              <th>AI SUGGESTION</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(expense => (
              <ExpenseRow
                key={expense.entry_id}
                expense={expense}
                suggestion={suggestionMap.get(expense.entry_id)}
                allCategories={allCategories}
                onCategoryChange={handleCategoryChange}
              />
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="et-empty">No expenses match the current filters.</div>
        )}
      </div>
    </div>
  );
}


interface RowProps {
  expense: Expense;
  suggestion?: CategorySuggestion;
  allCategories: string[];
  onCategoryChange: (expense: Expense, cat: string) => void;
}

function ExpenseRow({ expense, suggestion, allCategories, onCategoryChange }: RowProps) {
  const date = new Date(expense.date).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
  const confClass = suggestion ? (suggestion.confidence >= 0.85 ? 'conf-h' : suggestion.confidence >= 0.6 ? 'conf-m' : 'conf-l') : '';

  return (
    <tr className={expense.category === 'UNCATEGORIZED' ? 'row-uncat' : ''}>
      <td className="td-date mono">{date}</td>
      <td className="td-desc">{expense.description}</td>
      <td className="td-amt mono num">{expense.amount.toLocaleString('es-ES', { minimumFractionDigits: 2 })} {expense.currency}</td>
      <td className="td-payer">{expense.payer}</td>
      <td className="td-cat">
        <select
          value={expense.category}
          onChange={e => onCategoryChange(expense, e.target.value)}
          className={expense.category === 'UNCATEGORIZED' ? 'select-uncat' : ''}
        >
          <option value="UNCATEGORIZED">— Uncategorized —</option>
          {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </td>
      <td className="td-sug">
        {suggestion && (
          <button
            className={`sug-btn ${confClass}`}
            title={`${Math.round(suggestion.confidence * 100)}% — ${suggestion.reasoning}`}
            onClick={() => onCategoryChange(expense, suggestion.suggested_category)}
          >
            {suggestion.suggested_category}
            <span className="sug-pct">{Math.round(suggestion.confidence * 100)}%</span>
          </button>
        )}
      </td>
    </tr>
  );
}
