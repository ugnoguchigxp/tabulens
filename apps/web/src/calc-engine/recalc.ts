import { collectAffectedCells } from './dependency-graph';
import type { DependencyGraphState } from './types';

const CIRCULAR_ERROR = '#CIRC!';

export interface RecalcOps {
  hasFormula: (cellKey: string) => boolean;
  setComputedValue: (cellKey: string, value: unknown) => void;
  evaluateFormula: (cellKey: string) => unknown;
}

function detectCycles(
  graph: DependencyGraphState,
  formulaKeys: Set<string>,
): Set<string> {
  const visited = new Set<string>();
  const stack = new Set<string>();
  const cycles = new Set<string>();

  const walk = (cellKey: string) => {
    if (stack.has(cellKey)) {
      cycles.add(cellKey);
      return;
    }
    if (visited.has(cellKey)) {
      return;
    }

    visited.add(cellKey);
    stack.add(cellKey);

    const dependencies = graph.dependsOn.get(cellKey) ?? new Set<string>();
    dependencies.forEach((dependencyKey) => {
      if (!formulaKeys.has(dependencyKey)) {
        return;
      }
      if (stack.has(dependencyKey)) {
        stack.forEach((stackNode) => cycles.add(stackNode));
        cycles.add(dependencyKey);
        return;
      }
      walk(dependencyKey);
      if (cycles.has(dependencyKey)) {
        cycles.add(cellKey);
      }
    });

    stack.delete(cellKey);
  };

  formulaKeys.forEach((key) => walk(key));
  return cycles;
}

function topologicalFormulaOrder(
  graph: DependencyGraphState,
  formulaKeys: Set<string>,
): string[] {
  const indegree = new Map<string, number>();
  const dependents = new Map<string, Set<string>>();

  formulaKeys.forEach((key) => {
    indegree.set(key, 0);
    dependents.set(key, new Set<string>());
  });

  formulaKeys.forEach((key) => {
    const dependencies = graph.dependsOn.get(key) ?? new Set<string>();
    dependencies.forEach((dependencyKey) => {
      if (!formulaKeys.has(dependencyKey)) {
        return;
      }
      indegree.set(key, (indegree.get(key) ?? 0) + 1);
      const reverse = dependents.get(dependencyKey) ?? new Set<string>();
      reverse.add(key);
      dependents.set(dependencyKey, reverse);
    });
  });

  const queue: string[] = [];
  indegree.forEach((value, key) => {
    if (value === 0) {
      queue.push(key);
    }
  });

  const ordered: string[] = [];
  while (queue.length > 0) {
    const key = queue.shift();
    if (!key) {
      continue;
    }

    ordered.push(key);
    const reverse = dependents.get(key) ?? new Set<string>();
    reverse.forEach((dependentKey) => {
      const nextDegree = (indegree.get(dependentKey) ?? 0) - 1;
      indegree.set(dependentKey, nextDegree);
      if (nextDegree === 0) {
        queue.push(dependentKey);
      }
    });
  }

  if (ordered.length < formulaKeys.size) {
    formulaKeys.forEach((key) => {
      if (!ordered.includes(key)) {
        ordered.push(key);
      }
    });
  }

  return ordered;
}

export function recalcAffectedCells(
  graph: DependencyGraphState,
  changedKeys: string[],
  ops: RecalcOps,
): Set<string> {
  const affected = collectAffectedCells(graph, changedKeys);
  const formulaKeys = new Set<string>();
  affected.forEach((key) => {
    if (ops.hasFormula(key)) {
      formulaKeys.add(key);
    }
  });

  const cycleKeys = detectCycles(graph, formulaKeys);
  cycleKeys.forEach((key) => {
    ops.setComputedValue(key, CIRCULAR_ERROR);
  });

  const evaluableKeys = new Set<string>();
  formulaKeys.forEach((key) => {
    if (!cycleKeys.has(key)) {
      evaluableKeys.add(key);
    }
  });

  const ordered = topologicalFormulaOrder(graph, evaluableKeys);
  ordered.forEach((key) => {
    ops.setComputedValue(key, ops.evaluateFormula(key));
  });

  return affected;
}
