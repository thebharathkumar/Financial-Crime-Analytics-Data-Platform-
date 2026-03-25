package com.fcap.transformation;

import com.fcap.model.Transaction;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Applies normalisation, risk enrichment, and data quality rules to
 * {@link Transaction} objects during the ingestion pipeline.
 *
 * <p>All methods are stateless; the class is intended to be used as a singleton
 * bean in a Spring or CDI context, or instantiated directly in tests.
 */
public class TransactionTransformer {

    /**
     * Threshold above which a transaction is considered high-value for AML
     * reporting purposes (USD equivalent).
     */
    private static final BigDecimal HIGH_VALUE_THRESHOLD = new BigDecimal("10000");

    /**
     * Threshold above which an elevated risk score is applied.
     */
    private static final BigDecimal ELEVATED_RISK_THRESHOLD = new BigDecimal("50000");

    /**
     * Structuring detection window: transactions between this value and the
     * reporting threshold may indicate deliberate structuring.
     */
    private static final BigDecimal STRUCTURING_LOWER_BOUND = new BigDecimal("9000");

    // -------------------------------------------------------------------------
    // Public transformation methods
    // -------------------------------------------------------------------------

    /**
     * Normalises a transaction by:
     * <ul>
     *   <li>Converting the currency code to uppercase.</li>
     *   <li>Trimming whitespace from all string fields.</li>
     *   <li>Ensuring {@code flagged} defaults to {@code false} when null.</li>
     * </ul>
     *
     * @param t the transaction to normalise (not modified in place; a copy is returned)
     * @return a normalised copy of the transaction
     */
    public Transaction normalize(Transaction t) {
        Transaction normalised = copyTransaction(t);

        if (normalised.getCurrency() != null) {
            normalised.setCurrency(normalised.getCurrency().trim().toUpperCase());
        }
        if (normalised.getTransactionId() != null) {
            normalised.setTransactionId(normalised.getTransactionId().trim());
        }
        if (normalised.getSourceAccount() != null) {
            normalised.setSourceAccount(normalised.getSourceAccount().trim());
        }
        if (normalised.getDestinationAccount() != null) {
            normalised.setDestinationAccount(normalised.getDestinationAccount().trim());
        }
        if (normalised.getTransactionType() != null) {
            normalised.setTransactionType(normalised.getTransactionType().trim().toUpperCase());
        }
        if (normalised.getFlagged() == null) {
            normalised.setFlagged(Boolean.FALSE);
        }

        return normalised;
    }

    /**
     * Enriches a transaction with initial risk indicators:
     * <ul>
     *   <li>Flags the transaction if {@code amount >= 10,000}.</li>
     *   <li>Sets a baseline risk score based on amount thresholds.</li>
     * </ul>
     *
     * @param t the transaction to enrich
     * @return enriched copy of the transaction
     */
    public Transaction enrichWithRiskIndicators(Transaction t) {
        Transaction enriched = copyTransaction(t);

        if (enriched.getAmount() == null) {
            enriched.setRiskScore(0.0);
            return enriched;
        }

        BigDecimal amount = enriched.getAmount();

        // Flag high-value transactions
        if (amount.compareTo(HIGH_VALUE_THRESHOLD) >= 0) {
            enriched.setFlagged(Boolean.TRUE);
        }

        // Assign baseline risk score
        double riskScore;
        if (amount.compareTo(new BigDecimal("1000000")) >= 0) {
            riskScore = 90.0;
        } else if (amount.compareTo(new BigDecimal("500000")) >= 0) {
            riskScore = 75.0;
        } else if (amount.compareTo(ELEVATED_RISK_THRESHOLD) >= 0) {
            riskScore = 60.0;
        } else if (amount.compareTo(HIGH_VALUE_THRESHOLD) >= 0) {
            riskScore = 40.0;
        } else if (amount.compareTo(STRUCTURING_LOWER_BOUND) >= 0) {
            // Near-threshold: potential structuring indicator
            riskScore = 30.0;
        } else {
            riskScore = 10.0;
        }

        enriched.setRiskScore(riskScore);
        return enriched;
    }

    /**
     * Detects potential structuring patterns for a given account.
     *
     * <p>Structuring (also known as "smurfing") involves splitting a large sum
     * into multiple smaller transactions deliberately kept just below the
     * reporting threshold. This method flags transactions from/to
     * {@code accountId} where the amount falls in the range [9,000, 10,000).
     *
     * @param transactions all transactions to analyse
     * @param accountId    the account to focus on
     * @return list of transactions that match the structuring pattern
     */
    public List<Transaction> detectStructuring(List<Transaction> transactions, String accountId) {
        if (transactions == null || accountId == null) {
            return new ArrayList<>();
        }

        List<Transaction> candidates = transactions.stream()
                .filter(t -> accountId.equals(t.getSourceAccount())
                        || accountId.equals(t.getDestinationAccount()))
                .filter(t -> t.getAmount() != null
                        && t.getAmount().compareTo(STRUCTURING_LOWER_BOUND) >= 0
                        && t.getAmount().compareTo(HIGH_VALUE_THRESHOLD) < 0)
                .collect(Collectors.toList());

        // Flag and return qualifying transactions
        return candidates.stream()
                .map(t -> {
                    Transaction flagged = copyTransaction(t);
                    flagged.setFlagged(Boolean.TRUE);
                    // Boost risk score for structuring indicator
                    double boosted = flagged.getRiskScore() != null
                            ? Math.min(100.0, flagged.getRiskScore() + 20.0)
                            : 50.0;
                    flagged.setRiskScore(boosted);
                    return flagged;
                })
                .collect(Collectors.toList());
    }

    /**
     * Applies data quality rules to a transaction and returns a list of
     * violation messages.
     *
     * <p>Rules checked:
     * <ol>
     *   <li>transaction_id must not be null or blank.</li>
     *   <li>amount must not be null and must be positive.</li>
     *   <li>source_account must not be null or blank.</li>
     *   <li>destination_account must not be null or blank.</li>
     *   <li>currency must be exactly 3 characters.</li>
     *   <li>timestamp must not be null.</li>
     *   <li>source and destination accounts must not be identical.</li>
     * </ol>
     *
     * @param t the transaction to validate
     * @return list of violation strings; empty list indicates no violations
     */
    public List<String> applyDataQualityRules(Transaction t) {
        List<String> violations = new ArrayList<>();

        if (t.getTransactionId() == null || t.getTransactionId().isBlank()) {
            violations.add("VIOLATION: transaction_id is null or blank");
        }

        if (t.getAmount() == null) {
            violations.add("VIOLATION: amount is null");
        } else if (t.getAmount().compareTo(BigDecimal.ZERO) <= 0) {
            violations.add("VIOLATION: amount must be positive, got " + t.getAmount());
        }

        if (t.getSourceAccount() == null || t.getSourceAccount().isBlank()) {
            violations.add("VIOLATION: source_account is null or blank");
        }

        if (t.getDestinationAccount() == null || t.getDestinationAccount().isBlank()) {
            violations.add("VIOLATION: destination_account is null or blank");
        }

        if (t.getCurrency() == null || t.getCurrency().trim().length() != 3) {
            violations.add("VIOLATION: currency must be a 3-character ISO code, got '"
                    + t.getCurrency() + "'");
        }

        if (t.getTimestamp() == null) {
            violations.add("VIOLATION: timestamp is null");
        }

        if (t.getSourceAccount() != null && t.getDestinationAccount() != null
                && t.getSourceAccount().equalsIgnoreCase(t.getDestinationAccount())) {
            violations.add("VIOLATION: source_account and destination_account must differ");
        }

        return violations;
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Creates a shallow copy of a transaction to preserve immutability of
     * pipeline stages.
     */
    private static Transaction copyTransaction(Transaction source) {
        return Transaction.builder()
                .transactionId(source.getTransactionId())
                .sourceAccount(source.getSourceAccount())
                .destinationAccount(source.getDestinationAccount())
                .amount(source.getAmount())
                .currency(source.getCurrency())
                .timestamp(source.getTimestamp())
                .transactionType(source.getTransactionType())
                .riskScore(source.getRiskScore())
                .flagged(source.getFlagged())
                .build();
    }
}
