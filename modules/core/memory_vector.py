import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Simulacija vektorske baze za Termux resurse
class AtlasMemory:
    def __init__(self):
        self.memories = [] # Tekstualne uspomene
        self.vectors = []  # Vektorski prikazi

    def add_memory(self, text, vector):
        self.memories.append(text)
        self.vectors.append(vector)

    def retrieve(self, query_vector, top_k=3):
        if not self.vectors: return []
        similarities = cosine_similarity([query_vector], self.vectors)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [self.memories[i] for i in top_indices if similarities[i] > 0.7]

memory_vault = AtlasMemory()
