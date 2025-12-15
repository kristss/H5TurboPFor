#include <stdlib.h>
#include <stddef.h>
#include "turbopfor_h5plugin.h"
//#include "zstd.h"
#include <time.h>

#define TURBOPFOR_FILTER 62016

//#define DEBUG 1

#include "bitpack.h"
#include "vp4.h"
#include "vint.h"
#include "fp.h"
#include "eliasfano.h"
#include "vsimple.h"
#include "transpose.h"
#include "trle.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#ifdef __APPLE__
#include <sys/malloc.h>
#else
#include <malloc.h>
#endif
#ifdef _MSC_VER
#include "vs/getopt.h"
#else
#include <getopt.h>
#endif
#if defined(_WIN32)
#include <windows.h>
#define srand48(x) srand(x)
#define drand48() ((double)(rand()) / RAND_MAX)
#define __off64_t _off64_t
#endif
#include <math.h> // pow,fabs
#include <float.h>

#include "hdf5.h"

#include "conf.h"
#include "time_.h"
#define BITUTIL_IN
#include "bitutil.h"

#if defined(__i386__) || defined(__x86_64__)
#define SSE
#define AVX2
#elif defined(__ARM_NEON) || defined(__powerpc64__)
#define SSE
#endif

#ifndef min
#define min(x, y) (((x) < (y)) ? (x) : (y))
#define max(x, y) (((x) > (y)) ? (x) : (y))
#endif

#define CBUF(_n_) (((size_t)(_n_)) * 5 / 3 + 1024 /*1024*/)

typedef enum DataElementType
{
	ELEMENT_TYPE_SHORT = 0,
	ELEMENT_TYPE_USHORT = 1
} DataElementType;

void delta2d_encode(size_t length0, size_t length1, short* chunkBuffer) {
    if (length0 <= 1) {
        return;
    }
    size_t d0, d1;
    for (d0 = length0-1; d0 >= 1; d0--) {
        for (d1 = 0; d1 < length1; d1++) {
            chunkBuffer[d0*length1 + d1] -= chunkBuffer[(d0-1)*length1 + d1];
        }
    }
}

void delta2d_decode(size_t length0, size_t length1, short* chunkBuffer) {
    if (length0 <= 1) {
        return;
    }
    size_t d0, d1;
    for (d0 = 1; d0 < length0; d0++) {
        for (d1 = 0; d1 < length1; d1++) {
            chunkBuffer[d0*length1 + d1] += chunkBuffer[(d0-1)*length1 + d1];
        }
    }
}
#define SetBit(A, k) (A[(k / 32)] |= (1 << (k % 32)))
#define ClearBit(A, k) (A[(k / 32)] &= ~(1 << (k % 32)))
#define TestBit(A, k) (A[(k / 32)] & (1 << (k % 32)))

/**
 * @brief the filter for Turbopfor
 *
 * @param flags : is set by HDF5 for decompress or compress
 * @param cd_nelmts: the # of values in  cd_values
 * @param cd_values: the pointer of the parameter
 * 			cd_values[0]: type of data:  short (0),  int (1)
 *          cd_values[1]: scaling factor for encoding of short data type:
 *                        0: multiply by 1
 *                        1: multiply by 1
 *                        >=2: multiplication factor
 *
 *          cd_values[2, -]: size of each dimension of a chunk
 * @param nbytes : input data size
 * @param buf_size : output data size
 * @param buf : the pointer to data buffer
 * @return size_t
 */
DLL_EXPORT size_t turbopfor_filter(unsigned int flags, size_t cd_nelmts,
								   const unsigned int cd_values[], size_t nbytes,
								   size_t *buf_size, void **buf)
{

	size_t ret_value = 0;
	size_t origSize = nbytes; /* Number of bytes for output (compressed) buffer */
#ifdef DEBUG
	printf("cd_nelmts = %zu, cd_values = ", cd_nelmts);
	for (int i = 0; i < cd_nelmts; i++)
	{
		printf("%d , ", cd_values[i]);
	}
	printf("\n");
#endif

	unsigned m = 1;
	unsigned n, l;
	unsigned char *out;
	for (int i = 2; i < cd_nelmts; i++)
	{
		m = m * cd_values[i];
	}
	unsigned chunk0 = 1;
	unsigned chunk1 = cd_values[cd_nelmts-1];
	for (int i = 2; i < cd_nelmts-1; i++)
	{
		chunk0 = chunk0 * cd_values[i];
	}
	
    // Note: cd_values[1] (scalefactor) is ignored in this version.
    // Quantization should be performed before passing data to the filter.

	int32_t *A;
	int A_n;
#ifdef DEBUG
	clock_t t;
	t = clock();
#endif
	if (flags & H5Z_FLAG_REVERSE)
	{
		void *old_buf = *buf;
		switch (cd_values[0])
		{
		case ELEMENT_TYPE_SHORT:
		{
			n = m * sizeof(unsigned short);
			unsigned char *outbuf_short = (unsigned char *)malloc(CBUF(n) + 1024 * 1024);

			p4nzdec128v16((unsigned char *)*buf, m, (uint16_t *)outbuf_short);
			n = m * sizeof(short);
			out = (unsigned char *)malloc(n);
			
            // Copy decoded data to output buffer
            memcpy(out, outbuf_short, n);
            short *short_p = (short *)out;

            // Apply Delta Decoding
			delta2d_decode(chunk0, chunk1, short_p);
            
			free(outbuf_short);
			outbuf_short = NULL;
			break;
		}
		default:
			printf("Not supported data type yet !\n");
			// goto error; // Commented out because 'error' label is not defined
		}

#ifdef DEBUG
		t = clock() - t;
		double time_taken = ((double)t) / CLOCKS_PER_SEC; // in seconds
		printf("H5TurboPfor dec : cost %f seconds  \n", time_taken);
#endif
		if (old_buf != NULL)
			free(old_buf);
		*buf = out;
		ret_value = n;
	}
	else
	{
		switch (cd_values[0])
		{
		case ELEMENT_TYPE_SHORT:
		{
			n = m * sizeof(unsigned short);
			short *inbuf_short = *buf;
			
            // Apply Delta Encoding (In-Place)
			delta2d_encode(chunk0, chunk1, inbuf_short);

#ifdef DEBUG
			printf("Debug: decode A_n = %d, A[0, 1, 3]= %d, %d, %d\n", A_n, A[0], A[1], A[2]);
#endif

			out = (unsigned char *)malloc(CBUF(n) + 1024 * 1024);
			l = p4nzenc128v16(inbuf_short, m, out);
			break;
		}
		default:
			printf("Not supported data type yet !\n");
			goto error;
		}

#ifdef DEBUG
		t = clock() - t;
		double time_taken = ((double)t) / CLOCKS_PER_SEC; // in seconds
		printf("H5TurboPfor: ratio = %f (origSize =%u, compSize = %u byte), cost %f seconds  \n", (float)n / (float)l, n, l, time_taken);
#endif

		if (*buf != NULL)
			free(*buf);
		*buf = out;
		*buf_size = l;
		ret_value = l;
	}
	return ret_value;

error:
	return 0;
}

const H5Z_class_t turbopfor_H5Filter =
	{
		H5Z_CLASS_T_VERS,
		(H5Z_filter_t)(TURBOPFOR_FILTER),
		1, 1,
		"TurboPFor-Integer-Compression: https://github.com/dbinlbl/H5TurboPFor",
		NULL, NULL,
		(H5Z_func_t)(turbopfor_filter)};

DLL_EXPORT H5PL_type_t H5PLget_plugin_type(void)
{
	return H5PL_TYPE_FILTER;
}

DLL_EXPORT const void *H5PLget_plugin_info(void)
{
	return &turbopfor_H5Filter;
}
