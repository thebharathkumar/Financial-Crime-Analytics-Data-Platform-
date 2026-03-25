package com.fcap.pipeline;

import com.fcap.model.Transaction;
import com.fcap.transformation.TransactionTransformer;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

/**
 * Orchestrates the ingestion of raw transaction data through the AML processing
 * pipeline.
 *
 * <p>Pipeline stages:
 * <ol>
 *   <li><b>Normalise</b> — standardise field formatting and types.</li>
 *   <li><b>Enrich</b>    — apply risk indicators based on transaction attributes.</li>
 *   <li><b>Quality</b>   — validate records; quarantine those with violations.</li>
 * </ol>
 *
 * <p>Statistics are accumulated per run and available via {@link #getPipelineStats()}.
 */
public class DataIngestionPipeline {

    private final TransactionTransformer transformer;

    private final AtomicInteger totalProcessed   = new AtomicInteger(0);
    private final AtomicInteger totalNormalised  = new AtomicInteger(0);
    private final AtomicInteger totalEnriched    = new AtomicInteger(0);
    private final AtomicInteger totalQuarantined = new AtomicInteger(0);
    private final AtomicInteger totalOutput      = new AtomicInteger(0);

    private volatile long lastRunStartMs  = 0L;
    private volatile long lastRunEndMs    = 0L;

    public DataIngestionPipeline() {
        this.transformer = new TransactionTransformer();
    }

    public DataIngestionPipeline(TransactionTransformer transformer) {
        this.transformer = transformer;
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Processes a batch of raw transactions synchronously through all pipeline stages.
     *
     * <p>Records that fail data quality checks are quarantined (excluded from the
     * returned list) and counted in pipeline stats.
     *
     * @param rawTransactions unprocessed transactions from the source system
     * @return list of fully processed, quality-checked transactions
     */
    public List<Transaction> process(List<Transaction> rawTransactions) {
        if (rawTransactions == null || rawTransactions.isEmpty()) {
            return new ArrayList<>();
        }

        lastRunStartMs = Instant.now().toEpochMilli();
        totalProcessed.addAndGet(rawTransactions.size());

        // Stage 1: Normalise
        List<Transaction> normalised = rawTransactions.stream()
                .map(transformer::normalize)
                .collect(Collectors.toList());
        totalNormalised.addAndGet(normalised.size());

        // Stage 2: Enrich with risk indicators
        List<Transaction> enriched = normalised.stream()
                .map(transformer::enrichWithRiskIndicators)
                .collect(Collectors.toList());
        totalEnriched.addAndGet(enriched.size());

        // Stage 3: Data quality gate — quarantine failing records
        List<Transaction> output = new ArrayList<>();
        for (Transaction t : enriched) {
            List<String> violations = transformer.applyDataQualityRules(t);
            if (violations.isEmpty()) {
                output.add(t);
            } else {
                totalQuarantined.incrementAndGet();
            }
        }
        totalOutput.addAndGet(output.size());

        lastRunEndMs = Instant.now().toEpochMilli();
        return output;
    }

    /**
     * Asynchronously processes a batch of raw transactions.
     *
     * <p>Delegates to {@link #process(List)} on the common fork-join pool.  In
     * production this should be backed by a dedicated executor with configurable
     * thread-pool settings.
     *
     * @param rawTransactions unprocessed transactions
     * @return CompletableFuture resolving to the processed transaction list
     */
    public CompletableFuture<List<Transaction>> processAsync(List<Transaction> rawTransactions) {
        return CompletableFuture.supplyAsync(() -> process(rawTransactions));
    }

    /**
     * Returns a snapshot of pipeline execution statistics.
     *
     * <p>Counters are cumulative across all {@link #process} invocations since
     * this instance was created.
     *
     * @return map with keys: total_processed, total_normalised, total_enriched,
     *         total_quarantined, total_output, last_run_duration_ms
     */
    public Map<String, Object> getPipelineStats() {
        Map<String, Object> stats = new HashMap<>();
        stats.put("total_processed",   totalProcessed.get());
        stats.put("total_normalised",  totalNormalised.get());
        stats.put("total_enriched",    totalEnriched.get());
        stats.put("total_quarantined", totalQuarantined.get());
        stats.put("total_output",      totalOutput.get());
        long duration = lastRunEndMs > 0 ? lastRunEndMs - lastRunStartMs : 0L;
        stats.put("last_run_duration_ms", duration);
        return stats;
    }
}
