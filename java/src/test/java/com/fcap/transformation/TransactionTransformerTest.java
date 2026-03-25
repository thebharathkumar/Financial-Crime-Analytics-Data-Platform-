package com.fcap.transformation;

import com.fcap.model.Transaction;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link TransactionTransformer}.
 */
class TransactionTransformerTest {

    private TransactionTransformer transformer;

    @BeforeEach
    void setUp() {
        transformer = new TransactionTransformer();
    }

    // -------------------------------------------------------------------------
    // Helper builders
    // -------------------------------------------------------------------------

    private Transaction validTransaction(String id, BigDecimal amount) {
        return Transaction.builder()
                .transactionId(id)
                .sourceAccount("ACC-SRC-001")
                .destinationAccount("ACC-DST-001")
                .amount(amount)
                .currency("usd")
                .timestamp(LocalDateTime.now())
                .transactionType("wire")
                .flagged(false)
                .build();
    }

    // -------------------------------------------------------------------------
    // normalize
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("normalize: currency is uppercased")
    void testNormalize_currencyUppercased() {
        Transaction t = validTransaction("TXN-001", new BigDecimal("5000"));
        Transaction result = transformer.normalize(t);
        assertEquals("USD", result.getCurrency());
    }

    @Test
    @DisplayName("normalize: transaction type is uppercased")
    void testNormalize_transactionTypeUppercased() {
        Transaction t = validTransaction("TXN-002", new BigDecimal("1000"));
        Transaction result = transformer.normalize(t);
        assertEquals("WIRE", result.getTransactionType());
    }

    @Test
    @DisplayName("normalize: whitespace is trimmed from id")
    void testNormalize_whitespaceStripped() {
        Transaction t = Transaction.builder()
                .transactionId("  TXN-003  ")
                .sourceAccount("  ACC-SRC ")
                .destinationAccount("ACC-DST ")
                .amount(BigDecimal.ONE)
                .currency("USD")
                .timestamp(LocalDateTime.now())
                .build();
        Transaction result = transformer.normalize(t);
        assertEquals("TXN-003", result.getTransactionId());
        assertEquals("ACC-SRC", result.getSourceAccount());
    }

    @Test
    @DisplayName("normalize: null flagged defaults to false")
    void testNormalize_nullFlaggedDefaultsFalse() {
        Transaction t = Transaction.builder()
                .transactionId("TXN-004")
                .sourceAccount("SRC")
                .destinationAccount("DST")
                .amount(BigDecimal.TEN)
                .currency("USD")
                .timestamp(LocalDateTime.now())
                .flagged(null)
                .build();
        Transaction result = transformer.normalize(t);
        assertFalse(result.getFlagged());
    }

    // -------------------------------------------------------------------------
    // enrichWithRiskIndicators
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("enrich: high-amount transaction is flagged")
    void testEnrichWithRiskIndicators_highAmount() {
        Transaction t = validTransaction("TXN-005", new BigDecimal("15000"));
        Transaction result = transformer.enrichWithRiskIndicators(t);
        assertTrue(result.getFlagged());
        assertNotNull(result.getRiskScore());
        assertTrue(result.getRiskScore() >= 40.0);
    }

    @Test
    @DisplayName("enrich: low-amount transaction is not flagged")
    void testEnrichWithRiskIndicators_lowAmount() {
        Transaction t = validTransaction("TXN-006", new BigDecimal("500"));
        Transaction result = transformer.enrichWithRiskIndicators(t);
        assertFalse(result.getFlagged());
        assertEquals(10.0, result.getRiskScore());
    }

    @Test
    @DisplayName("enrich: million-dollar transaction gets max risk score tier")
    void testEnrichWithRiskIndicators_millionDollar() {
        Transaction t = validTransaction("TXN-007", new BigDecimal("1500000"));
        Transaction result = transformer.enrichWithRiskIndicators(t);
        assertEquals(90.0, result.getRiskScore());
    }

    @Test
    @DisplayName("enrich: null amount results in risk score 0")
    void testEnrichWithRiskIndicators_nullAmount() {
        Transaction t = Transaction.builder()
                .transactionId("TXN-008")
                .sourceAccount("SRC")
                .destinationAccount("DST")
                .currency("USD")
                .timestamp(LocalDateTime.now())
                .amount(null)
                .build();
        Transaction result = transformer.enrichWithRiskIndicators(t);
        assertEquals(0.0, result.getRiskScore());
    }

    // -------------------------------------------------------------------------
    // detectStructuring
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("detectStructuring: identifies near-threshold transactions")
    void testDetectStructuring() {
        List<Transaction> transactions = Arrays.asList(
                validTransaction("TXN-S01", new BigDecimal("9500")),   // structuring
                validTransaction("TXN-S02", new BigDecimal("9800")),   // structuring
                validTransaction("TXN-S03", new BigDecimal("12000")),  // above threshold
                validTransaction("TXN-S04", new BigDecimal("500"))     // well below
        );

        List<Transaction> structuring = transformer.detectStructuring(transactions, "ACC-SRC-001");
        assertEquals(2, structuring.size());
        structuring.forEach(t -> assertTrue(t.getFlagged()));
    }

    @Test
    @DisplayName("detectStructuring: null account returns empty list")
    void testDetectStructuring_nullAccount() {
        List<Transaction> transactions = List.of(validTransaction("T1", new BigDecimal("9500")));
        List<Transaction> result = transformer.detectStructuring(transactions, null);
        assertTrue(result.isEmpty());
    }

    // -------------------------------------------------------------------------
    // applyDataQualityRules
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("applyDataQualityRules: valid transaction has no violations")
    void testApplyDataQualityRules_validTransaction() {
        Transaction t = validTransaction("TXN-DQ01", new BigDecimal("1000"));
        List<String> violations = transformer.applyDataQualityRules(t);
        assertTrue(violations.isEmpty());
    }

    @Test
    @DisplayName("applyDataQualityRules: missing id produces violation")
    void testApplyDataQualityRules_missingId() {
        Transaction t = Transaction.builder()
                .transactionId(null)
                .sourceAccount("SRC")
                .destinationAccount("DST")
                .amount(new BigDecimal("100"))
                .currency("USD")
                .timestamp(LocalDateTime.now())
                .build();
        List<String> violations = transformer.applyDataQualityRules(t);
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.contains("transaction_id")));
    }

    @Test
    @DisplayName("applyDataQualityRules: negative amount produces violation")
    void testApplyDataQualityRules_negativeAmount() {
        Transaction t = validTransaction("TXN-DQ02", new BigDecimal("-500"));
        List<String> violations = transformer.applyDataQualityRules(t);
        assertTrue(violations.stream().anyMatch(v -> v.contains("amount")));
    }

    @Test
    @DisplayName("applyDataQualityRules: same source and destination triggers violation")
    void testApplyDataQualityRules_sameSourceDestination() {
        Transaction t = Transaction.builder()
                .transactionId("TXN-DQ03")
                .sourceAccount("ACC-SAME")
                .destinationAccount("ACC-SAME")
                .amount(new BigDecimal("100"))
                .currency("USD")
                .timestamp(LocalDateTime.now())
                .build();
        List<String> violations = transformer.applyDataQualityRules(t);
        assertTrue(violations.stream().anyMatch(v -> v.contains("differ")));
    }

    @Test
    @DisplayName("applyDataQualityRules: invalid currency produces violation")
    void testApplyDataQualityRules_invalidCurrency() {
        Transaction t = Transaction.builder()
                .transactionId("TXN-DQ04")
                .sourceAccount("SRC")
                .destinationAccount("DST")
                .amount(new BigDecimal("100"))
                .currency("EURO")   // 4 chars — invalid
                .timestamp(LocalDateTime.now())
                .build();
        List<String> violations = transformer.applyDataQualityRules(t);
        assertTrue(violations.stream().anyMatch(v -> v.contains("currency")));
    }
}
