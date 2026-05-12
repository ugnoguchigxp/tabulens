import type { DependencyGraphState } from './types';

function cloneSet(source: Set<string>): Set<string> {
  return new Set(source);
}

export function createDependencyGraph(): DependencyGraphState {
  return {
    dependsOn: new Map<string, Set<string>>(),
    dependents: new Map<string, Set<string>>(),
  };
}

export function cloneDependencyGraph(graph: DependencyGraphState): DependencyGraphState {
  const dependsOn = new Map<string, Set<string>>();
  const dependents = new Map<string, Set<string>>();

  graph.dependsOn.forEach((deps, key) => {
    dependsOn.set(key, cloneSet(deps));
  });
  graph.dependents.forEach((deps, key) => {
    dependents.set(key, cloneSet(deps));
  });

  return { dependsOn, dependents };
}

function deleteFromDependents(graph: DependencyGraphState, sourceKey: string): void {
  const previousDeps = graph.dependsOn.get(sourceKey);
  if (!previousDeps) {
    return;
  }

  previousDeps.forEach((dependencyKey) => {
    const reverse = graph.dependents.get(dependencyKey);
    if (!reverse) {
      return;
    }
    reverse.delete(sourceKey);
    if (reverse.size === 0) {
      graph.dependents.delete(dependencyKey);
    }
  });
}

export function setDependencies(graph: DependencyGraphState, sourceKey: string, dependencies: Set<string>): void {
  deleteFromDependents(graph, sourceKey);

  if (dependencies.size === 0) {
    graph.dependsOn.delete(sourceKey);
    return;
  }

  graph.dependsOn.set(sourceKey, cloneSet(dependencies));

  dependencies.forEach((dependencyKey) => {
    const reverse = graph.dependents.get(dependencyKey) ?? new Set<string>();
    reverse.add(sourceKey);
    graph.dependents.set(dependencyKey, reverse);
  });
}

export function removeDependencies(graph: DependencyGraphState, sourceKey: string): void {
  deleteFromDependents(graph, sourceKey);
  graph.dependsOn.delete(sourceKey);
}

export function collectAffectedCells(graph: DependencyGraphState, changedKeys: string[]): Set<string> {
  const affected = new Set<string>();
  const queue = [...changedKeys];

  while (queue.length > 0) {
    const key = queue.shift();
    if (!key || affected.has(key)) {
      continue;
    }

    affected.add(key);
    const dependents = graph.dependents.get(key);
    if (!dependents) {
      continue;
    }

    dependents.forEach((dependentKey) => {
      if (!affected.has(dependentKey)) {
        queue.push(dependentKey);
      }
    });
  }

  return affected;
}
