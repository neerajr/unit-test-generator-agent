package com.example.app.service;

import java.util.List;
import java.util.Optional;

/**
 * Sample Spring Boot service for chunker smoke test.
 */
public class SampleService {

    private final SampleRepository repository;

    public SampleService(SampleRepository repository) {
        this.repository = repository;
    }

    /**
     * Finds an item by its identifier.
     *
     * @param id the item identifier
     * @return the found item
     * @throws IllegalArgumentException if id is null
     */
    public Item findById(Long id) {
        if (id == null) {
            throw new IllegalArgumentException("id must not be null");
        }
        return repository.findById(id)
                .orElseThrow(() -> new RuntimeException("Item not found: " + id));
    }

    /**
     * Returns all active items.
     */
    public List<Item> findAllActive() {
        return repository.findByActiveTrue();
    }

    /**
     * Creates a new item after validating input.
     */
    public Item create(String name, String description) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }
        Item item = new Item();
        item.setName(name.trim());
        item.setDescription(description);
        item.setActive(true);
        return repository.save(item);
    }

    /**
     * Soft-deletes an item by setting active = false.
     */
    public void delete(Long id) {
        Item item = findById(id);
        item.setActive(false);
        repository.save(item);
    }
}
