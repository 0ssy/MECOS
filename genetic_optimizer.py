"""
MECOS Phase 7 - Genetic Optimizer
Evolutionary algorithm for hyperparameter optimization, strategy evolution,
and configuration search using selection, crossover, and mutation operators.
"""

import asyncio
import json
import random
import copy
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Tuple
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings


class Individual:
    """A single candidate solution in the genetic population."""

    def __init__(self, genome: Dict[str, Any], fitness: float = 0.0):
        self.genome = genome
        self.fitness = fitness
        self.generation = 0
        self.id = f"ind_{random.randint(10000, 99999)}"

    def copy(self) -> "Individual":
        ind = Individual(copy.deepcopy(self.genome), self.fitness)
        ind.generation = self.generation
        return ind

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "genome": self.genome,
            "fitness": self.fitness,
            "generation": self.generation,
        }


class GeneticOptimizer:
    """
    Genetic algorithm for optimizing configurations and hyperparameters.
    Supports continuous, discrete, and categorical gene types.
    """

    def __init__(
        self,
        memory: MemorySystem,
        population_size: int = 20,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.7,
        elite_fraction: float = 0.1,
    ):
        self.memory = memory
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = max(1, int(population_size * elite_fraction))
        self.population: List[Individual] = []
        self.generation = 0
        self.best_individual: Optional[Individual] = None
        self.fitness_history: List[float] = []

        self.save_dir = settings.MEMORY_DIR / "evolution"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"GeneticOptimizer initialized (pop={population_size}, mut={mutation_rate})")

    def initialize_population(self, genome_template: Dict[str, Any]) -> List[Individual]:
        """
        Initialize a random population based on a genome template.
        Template format: {param_name: {"type": "float|int|choice", "min": ..., "max": ..., "choices": [...]}}
        """
        self.population = []
        for _ in range(self.population_size):
            genome = self._random_genome(genome_template)
            self.population.append(Individual(genome))
        logger.info(f"Population initialized: {self.population_size} individuals")
        return self.population

    def _random_genome(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a random genome from a template."""
        genome = {}
        for param, spec in template.items():
            if spec["type"] == "float":
                genome[param] = random.uniform(spec["min"], spec["max"])
            elif spec["type"] == "int":
                genome[param] = random.randint(int(spec["min"]), int(spec["max"]))
            elif spec["type"] == "choice":
                genome[param] = random.choice(spec["choices"])
            elif spec["type"] == "bool":
                genome[param] = random.choice([True, False])
        return genome

    def _mutate(self, individual: Individual, template: Dict[str, Any]) -> Individual:
        """Apply random mutations to an individual's genome."""
        mutated = individual.copy()
        for param, spec in template.items():
            if random.random() < self.mutation_rate:
                if spec["type"] == "float":
                    range_size = spec["max"] - spec["min"]
                    delta = random.gauss(0, range_size * 0.1)
                    mutated.genome[param] = max(spec["min"], min(spec["max"], mutated.genome[param] + delta))
                elif spec["type"] == "int":
                    delta = random.randint(-2, 2)
                    mutated.genome[param] = max(int(spec["min"]), min(int(spec["max"]), mutated.genome[param] + delta))
                elif spec["type"] == "choice":
                    mutated.genome[param] = random.choice(spec["choices"])
                elif spec["type"] == "bool":
                    mutated.genome[param] = not mutated.genome[param]
        return mutated

    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Uniform crossover between two parents."""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        child1_genome = {}
        child2_genome = {}
        for param in parent1.genome:
            if random.random() < 0.5:
                child1_genome[param] = parent1.genome[param]
                child2_genome[param] = parent2.genome.get(param, parent1.genome[param])
            else:
                child1_genome[param] = parent2.genome.get(param, parent1.genome[param])
                child2_genome[param] = parent1.genome[param]

        return Individual(child1_genome), Individual(child2_genome)

    def _tournament_select(self, k: int = 3) -> Individual:
        """Tournament selection: pick k random individuals, return the best."""
        candidates = random.sample(self.population, min(k, len(self.population)))
        return max(candidates, key=lambda ind: ind.fitness)

    async def evolve(
        self,
        fitness_fn: Callable[[Dict[str, Any]], float],
        genome_template: Dict[str, Any],
        n_generations: int = 10,
    ) -> Individual:
        """
        Run the genetic algorithm for n_generations.
        fitness_fn: callable that takes a genome dict and returns a float score.
        """
        if not self.population:
            self.initialize_population(genome_template)

        for gen in range(n_generations):
            self.generation = gen + 1

            # Evaluate fitness
            for ind in self.population:
                if ind.fitness == 0.0:
                    ind.fitness = fitness_fn(ind.genome)
                    ind.generation = self.generation

            # Sort by fitness
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            best = self.population[0]
            self.fitness_history.append(best.fitness)

            if self.best_individual is None or best.fitness > self.best_individual.fitness:
                self.best_individual = best.copy()

            logger.info(f"Gen {self.generation}: best_fitness={best.fitness:.4f}, genome={best.genome}")

            # Elitism: keep top individuals
            new_population = [ind.copy() for ind in self.population[:self.elite_size]]

            # Fill rest with offspring
            while len(new_population) < self.population_size:
                p1 = self._tournament_select()
                p2 = self._tournament_select()
                c1, c2 = self._crossover(p1, p2)
                c1 = self._mutate(c1, genome_template)
                c2 = self._mutate(c2, genome_template)
                new_population.extend([c1, c2])

            self.population = new_population[:self.population_size]

        # Save results
        self._save_results()
        await self.memory.add_experience(
            f"GENETIC EVOLUTION: {n_generations} generations, "
            f"best_fitness={self.best_individual.fitness:.4f}, "
            f"genome={self.best_individual.genome}",
            source="genetic_optimizer",
        )
        return self.best_individual

    def _save_results(self):
        path = self.save_dir / "evolution_results.json"
        data = {
            "generation": self.generation,
            "best": self.best_individual.to_dict() if self.best_individual else None,
            "fitness_history": self.fitness_history,
            "timestamp": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, default=str))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "generation": self.generation,
            "population_size": len(self.population),
            "best_fitness": self.best_individual.fitness if self.best_individual else 0.0,
            "best_genome": self.best_individual.genome if self.best_individual else {},
            "fitness_history": self.fitness_history[-10:],
        }
